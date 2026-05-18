import { lazy, Suspense } from "react";
import { Routes, Route, Navigate, useParams } from "react-router-dom";
import { ProtectedRoute, PublicRoute } from "../components/guards/RouteGuards";

// Redirect helper: maps the legacy standalone parent child sub-routes
// (/parent/child/:childId, /schedule, /homework, /behaviour) onto the unified
// Student Profile hub at /parent/children with the matching active tab.
const ParentStudentTabRedirect = ({ tab }) => {
  const { childId } = useParams();
  return <Navigate to={`/parent/children?child=${childId}&tab=${tab}`} replace />;
};

// --- Eager: small + first-paint critical (no recharts/jspdf chains) ---
import { LandingPage } from "../pages/LandingPage";
import { LoginPage } from "../pages/LoginPage";

// --- Lazy: every other page becomes its own chunk ---
// Webpack dedupes shared modules across these chunks, so heavy deps (recharts,
// jspdf, html2canvas, etc.) are downloaded only when a route that needs them
// is actually visited.

const RegisterPage = lazy(() => import("../pages/RegisterPage").then(m => ({ default: m.RegisterPage })));
const TeacherSelfRegistration = lazy(() => import("../pages/TeacherSelfRegistration").then(m => ({ default: m.TeacherSelfRegistration })));
const RegistrationConfirmationPage = lazy(() => import("../pages/RegistrationConfirmationPage"));
const ForgotPasswordPage = lazy(() => import("../pages/ForgotPasswordPage"));
const ResetPasswordPage = lazy(() => import("../pages/ResetPasswordPage"));
const ForcePasswordChange = lazy(() => import("../pages/ForcePasswordChange"));
// Spec §5.1 IT first-login MFA enrolment surface (mounted under
// /auth/mfa/enroll — the redirect target referenced by RouteGuards,
// LoginPage.resolveRedirectTarget, RegisterPage, and the IT onboarding
// wizard's mfa_enrollment_required handler).
const MfaEnrollPage = lazy(() => import("../pages/MfaEnrollPage"));
// Task #206 — public parent-invitation accept landing (IT §6.2c).
const ParentInvitationAcceptPage = lazy(() => import("../pages/ParentInvitationAcceptPage"));
// Task #210 — IT §6.7 cross-workspace collaborator accept landing.
const CollabInvitationAcceptPage = lazy(() => import("../pages/CollabInvitationAcceptPage"));
const AccountErasedPage = lazy(() => import("../pages/AccountErasedPage"));
const PrivacyPolicyPage = lazy(() => import("../pages/PrivacyPolicyPage"));
const TermsAndConditionsPage = lazy(() => import("../pages/TermsAndConditionsPage"));

// Heavy: AdminDashboard pulls recharts
const AdminDashboard = lazy(() => import("../pages/AdminDashboard").then(m => ({ default: m.AdminDashboard })));
const SchoolDashboard = lazy(() => import("../pages/SchoolDashboard").then(m => ({ default: m.SchoolDashboard })));
const TeacherDashboard = lazy(() => import("../pages/TeacherDashboard"));
const ParentDashboard = lazy(() => import("../pages/ParentDashboard"));
const PrincipalDashboard = lazy(() => import("../pages/PrincipalDashboard"));

const TeachersPage = lazy(() => import("../pages/TeachersPage").then(m => ({ default: m.TeachersPage })));
const UsersClassesManagement = lazy(() => import("../pages/UsersClassesManagement"));
const ClassDetailPage = lazy(() => import("../pages/ClassDetailPage"));
const AdminStudentProfilePage = lazy(() => import("../pages/StudentProfilePage"));
const StudentsPage = lazy(() => import("../pages/StudentsPage").then(m => ({ default: m.StudentsPage })));
const ClassesPage = lazy(() => import("../pages/ClassesPage").then(m => ({ default: m.ClassesPage })));
const SubjectsPage = lazy(() => import("../pages/SubjectsPage").then(m => ({ default: m.SubjectsPage })));
const SchedulePageNew = lazy(() => import("../pages/SchedulePageNew"));
const StandbyRosterPage = lazy(() => import("../pages/StandbyRosterPage"));
const TimeSlotsPage = lazy(() => import("../pages/TimeSlotsPage").then(m => ({ default: m.TimeSlotsPage })));
const TeacherAssignmentsPage = lazy(() => import("../pages/TeacherAssignmentsPage").then(m => ({ default: m.TeacherAssignmentsPage })));
const AttendancePage = lazy(() => import("../pages/AttendancePage").then(m => ({ default: m.AttendancePage })));
const TeacherAttendancePage = lazy(() => import("../pages/TeacherAttendancePage").then(m => ({ default: m.TeacherAttendancePage })));
const AssessmentPage = lazy(() => import("../pages/AssessmentPage").then(m => ({ default: m.AssessmentPage })));
const NotificationsPage = lazy(() => import("../pages/NotificationsPage").then(m => ({ default: m.NotificationsPage })));

// Teacher Module barrel — webpack will share the underlying module across these chunks
const TeacherHomePage = lazy(() => import("../pages/TeacherModule").then(m => ({ default: m.TeacherHomePage })));
const TeacherResponsiveDashboard = lazy(() => import("../pages/TeacherModule").then(m => ({ default: m.TeacherResponsiveDashboard })));
const SessionStartPage = lazy(() => import("../pages/TeacherModule").then(m => ({ default: m.SessionStartPage })));
const SessionTeachPage = lazy(() => import("../pages/TeacherModule").then(m => ({ default: m.SessionTeachPage })));
const TeacherSchedulePage = lazy(() => import("../pages/TeacherModule").then(m => ({ default: m.TeacherSchedulePage })));
const TeacherClassesPage = lazy(() => import("../pages/TeacherModule").then(m => ({ default: m.TeacherClassesPage })));
const TeacherClassDetailPage = lazy(() => import("../pages/TeacherModule").then(m => ({ default: m.TeacherClassDetailPage })));
const TeacherTasksPage = lazy(() => import("../pages/TeacherModule").then(m => ({ default: m.TeacherTasksPage })));
const TeacherAttendanceManagePage = lazy(() => import("../pages/TeacherModule").then(m => ({ default: m.TeacherAttendanceManagePage })));
const TeacherAssessmentsPage = lazy(() => import("../pages/TeacherModule").then(m => ({ default: m.TeacherAssessmentsPage })));
const TeacherBehaviorPage = lazy(() => import("../pages/TeacherModule").then(m => ({ default: m.TeacherBehaviorPage })));
const TeacherStudentsPage = lazy(() => import("../pages/TeacherModule").then(m => ({ default: m.TeacherStudentsPage })));
const ImportStudentsPage = lazy(() => import("../pages/TeacherModule").then(m => ({ default: m.ImportStudentsPage })));
const BulkImportPage = lazy(() => import("../pages/TeacherModule").then(m => ({ default: m.BulkImportPage })));
const TeacherAchievementsPage = lazy(() => import("../pages/TeacherModule").then(m => ({ default: m.TeacherAchievementsPage })));
const TeacherCommunicationPage = lazy(() => import("../pages/TeacherModule").then(m => ({ default: m.TeacherCommunicationPage })));
const TeacherResourcesPage = lazy(() => import("../pages/TeacherModule").then(m => ({ default: m.TeacherResourcesPage })));
const WorkspaceSettingsPage = lazy(() => import("../pages/TeacherModule").then(m => ({ default: m.WorkspaceSettingsPage })));
const WorkspaceSchedulePage = lazy(() => import("../pages/TeacherModule").then(m => ({ default: m.WorkspaceSchedulePage })));
const TeacherPersonalCalendarPage = lazy(() => import("../pages/TeacherModule").then(m => ({ default: m.TeacherPersonalCalendarPage })));
const LessonPlannerPage = lazy(() => import("../pages/TeacherModule").then(m => ({ default: m.LessonPlannerPage })));
const TeacherSubjectsPage = lazy(() => import("../pages/TeacherModule").then(m => ({ default: m.TeacherSubjectsPage })));
const TeacherAuditLogPage = lazy(() => import("../pages/TeacherModule").then(m => ({ default: m.TeacherAuditLogPage })));
const TeacherAnalyticsPage = lazy(() => import("../pages/TeacherModule").then(m => ({ default: m.TeacherAnalyticsPage })));
const TeacherNotificationsPage = lazy(() => import("../pages/TeacherModule").then(m => ({ default: m.TeacherNotificationsPage })));

const ProductHubPage = lazy(() => import("../pages/ProductHubPage").then(m => ({ default: m.ProductHubPage })));
const ProductHubSubmitPage = lazy(() => import("../pages/ProductHubSubmitPage").then(m => ({ default: m.ProductHubSubmitPage })));
const ProductHubIssuePage = lazy(() => import("../pages/ProductHubIssuePage").then(m => ({ default: m.ProductHubIssuePage })));

const PlatformSchoolsPage = lazy(() => import("../pages/PlatformSchoolsPage").then(m => ({ default: m.PlatformSchoolsPage })));
const PlatformSchoolDetailPage = lazy(() => import("../pages/PlatformSchoolDetailPage"));
const PlatformUsersPage = lazy(() => import("../pages/PlatformUsersPage").then(m => ({ default: m.PlatformUsersPage })));
const PlatformNotificationsPage = lazy(() => import("../pages/PlatformNotificationsPage").then(m => ({ default: m.PlatformNotificationsPage })));
const PlatformSettingsPage = lazy(() => import("../pages/PlatformSettingsPage").then(m => ({ default: m.PlatformSettingsPage })));
const RulesManagementPage = lazy(() => import("../pages/RulesManagementPage").then(m => ({ default: m.RulesManagementPage })));
// Task #225 — IT §6.8 platform-admin hard-delete UI for archived workspaces.
const PlatformWorkspacePurgePage = lazy(() => import("../pages/PlatformWorkspacePurgePage").then(m => ({ default: m.PlatformWorkspacePurgePage })));
// Heavy: SystemMonitoringPage pulls recharts
const SystemMonitoringPage = lazy(() => import("../pages/SystemMonitoringPage").then(m => ({ default: m.SystemMonitoringPage })));
const IntegrationsPage = lazy(() => import("../pages/IntegrationsPage"));
// Heavy: SecurityCenterPage already dynamic-imports jspdf+html2canvas at click time
const SecurityCenterPage = lazy(() => import("../pages/SecurityCenterPage"));
const CommunicationNotificationsPage = lazy(() => import("../pages/CommunicationNotificationsPage").then(m => ({ default: m.CommunicationNotificationsPage })));
const CommunicationCenterPage = lazy(() => import("../pages/CommunicationCenterPage").then(m => ({ default: m.CommunicationCenterPage })));
const TenantsManagement = lazy(() => import("../pages/TenantsManagement"));
const TeacherClassAssignmentPage = lazy(() => import("../pages/TeacherClassAssignmentPage"));
const IndependentTeacherOnboardingWizard = lazy(() => import("../pages/IndependentTeacherOnboardingWizard"));

const SchoolSettingsPagePro = lazy(() => import("../pages/SchoolSettingsPagePro"));
const AIInsightsPage = lazy(() => import("../pages/AIInsightsPage").then(m => ({ default: m.AIInsightsPage })));
const AccountSettingsPage = lazy(() => import("../pages/AccountSettingsPage").then(m => ({ default: m.AccountSettingsPage })));
const UsersManagement = lazy(() => import("../pages/UsersManagement"));
const UserDetailsPage = lazy(() => import("../pages/UserDetailsPage"));
const AuditLogsPage = lazy(() => import("../pages/AuditLogsPage"));

// Student Portal barrel — recharts via StudentTabsContent stays in student chunks only
const StudentPortalDashboard = lazy(() => import("../pages/StudentPortal").then(m => ({ default: m.StudentPortalDashboard })));
const StudentSchedulePage = lazy(() => import("../pages/StudentPortal").then(m => ({ default: m.StudentSchedulePage })));
const StudentGradesPage = lazy(() => import("../pages/StudentPortal").then(m => ({ default: m.StudentGradesPage })));
const StudentAttendancePage = lazy(() => import("../pages/StudentPortal").then(m => ({ default: m.StudentAttendancePage })));
const StudentProfilePage = lazy(() => import("../pages/StudentPortal").then(m => ({ default: m.StudentProfilePage })));
const StudentProgressPage = lazy(() => import("../pages/StudentPortal").then(m => ({ default: m.StudentProgressPage })));
const StudentAchievementsPage = lazy(() => import("../pages/StudentPortal").then(m => ({ default: m.StudentAchievementsPage })));

// Parent Portal barrel — recharts via parent/AnalyticsCharts + WeeklyStory stays in parent chunks only
const ParentPortalDashboard = lazy(() => import("../pages/ParentPortal").then(m => ({ default: m.ParentPortalDashboard })));
const ChildDetailsPage = lazy(() => import("../pages/ParentPortal").then(m => ({ default: m.ChildDetailsPage })));
const ChildSchedulePage = lazy(() => import("../pages/ParentPortal").then(m => ({ default: m.ChildSchedulePage })));
const ParentChildrenPage = lazy(() => import("../pages/ParentPortal").then(m => ({ default: m.ParentChildrenPage })));
const ChildBehaviorPage = lazy(() => import("../pages/ParentPortal").then(m => ({ default: m.ChildBehaviorPage })));
const ChildHomeworkPage = lazy(() => import("../pages/ParentPortal").then(m => ({ default: m.ChildHomeworkPage })));
const ParentMessagesPage = lazy(() => import("../pages/ParentPortal").then(m => ({ default: m.ParentMessagesPage })));
const ParentMeetingRequestPage = lazy(() => import("../pages/ParentPortal").then(m => ({ default: m.ParentMeetingRequestPage })));
const ParentSettingsPage = lazy(() => import("../pages/ParentPortal").then(m => ({ default: m.ParentSettingsPage })));
const ParentLegalDocumentPage = lazy(() => import("../pages/ParentPortal").then(m => ({ default: m.ParentLegalDocumentPage })));
const ParentCommunicationCenter = lazy(() => import("../pages/ParentPortal").then(m => ({ default: m.ParentCommunicationCenter })));
const ParentStudentAnalyticsPage = lazy(() => import("../pages/ParentPortal").then(m => ({ default: m.StudentAnalyticsPage })));

const SCHOOL_ROLES = ['school_principal', 'school_admin', 'school_sub_admin'];
const SCHOOL_PRINCIPAL_ROLES = ['school_principal', 'school_admin'];
const TEACHER_ROLES = ['teacher', 'independent_teacher'];
const SCHOOL_TEACHING_ROLES = [...SCHOOL_ROLES, ...TEACHER_ROLES];
const ALL_AUTHENTICATED_ROLES = ['platform_admin', ...SCHOOL_ROLES, ...TEACHER_ROLES, 'student', 'parent'];
const PRODUCT_HUB_ROLES = ['platform_admin', 'platform_operations_manager', 'school_principal', 'school_admin', 'teacher'];

// Lightweight RTL-aware fallback shown while a route chunk is loading.
function RouteFallback() {
  return (
    <div
      dir="rtl"
      style={{
        minHeight: "60vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
      aria-busy="true"
      aria-live="polite"
    >
      <div
        style={{
          width: 40,
          height: 40,
          border: "3px solid #e5e7eb",
          borderTopColor: "#0ea5e9",
          borderRadius: "50%",
          animation: "nassaq-spin 0.9s linear infinite",
        }}
      />
      <style>{`@keyframes nassaq-spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

export default function AppRoutes() {
  return (
    <Suspense fallback={<RouteFallback />}>
      <Routes>
        {/* Public Routes */}
        <Route path="/" element={<LandingPage />} />
        <Route path="/privacy" element={<PrivacyPolicyPage />} />
        <Route path="/terms" element={<TermsAndConditionsPage />} />
        <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
        <Route path="/register" element={<PublicRoute><RegisterPage /></PublicRoute>} />
        <Route path="/registration-confirmation" element={<RegistrationConfirmationPage />} />
        <Route path="/forgot-password" element={<PublicRoute><ForgotPasswordPage /></PublicRoute>} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/teacher-register" element={<TeacherSelfRegistration />} />
        {/* Task #206 — IT §6.2c public parent-invitation landing. The
            page swaps the one-shot bearer for an authenticated session
            and deep-links into /parent?student_id=…. Unauthenticated
            access is intentional — the token in the URL is the auth. */}
        <Route path="/parent-invitations/accept" element={<ParentInvitationAcceptPage />} />
        <Route path="/teacher/collab-accept" element={<CollabInvitationAcceptPage />} />
        {/* Task #276 — public landing after IT account-erasure request.
            The session is force-logged-out before redirect, so this
            page renders without auth and surfaces the deadline copy. */}
        <Route path="/account-erased" element={<AccountErasedPage />} />
        <Route path="/workspace-collaborators/accept" element={<CollabInvitationAcceptPage />} />

        {/* Force Password Change */}
        <Route path="/change-password" element={
          <ProtectedRoute skipPasswordCheck={true}><ForcePasswordChange /></ProtectedRoute>
        } />

        {/* Spec §5.1 — IT first-login MFA enrolment. ProtectedRoute's IT
            gate explicitly whitelists pathnames that start with /auth/mfa
            so the page can render without re-bouncing to itself. */}
        <Route path="/auth/mfa/enroll" element={
          <ProtectedRoute skipPasswordCheck={true}><MfaEnrollPage /></ProtectedRoute>
        } />

        {/* Platform Admin Routes */}
        <Route path="/admin" element={
          <ProtectedRoute allowedRoles={['platform_admin', 'platform_operations_manager']}><AdminDashboard /></ProtectedRoute>
        } />
        <Route path="/admin/schools" element={
          <ProtectedRoute allowedRoles={['platform_admin']}><TenantsManagement /></ProtectedRoute>
        } />
        <Route path="/admin/tenants" element={
          <ProtectedRoute allowedRoles={['platform_admin']}><TenantsManagement /></ProtectedRoute>
        } />
        <Route path="/admin/schools-table" element={
          <ProtectedRoute allowedRoles={['platform_admin']}><PlatformSchoolsPage /></ProtectedRoute>
        } />
        <Route path="/platform/schools/:schoolId" element={
          <ProtectedRoute allowedRoles={['platform_admin']}><PlatformSchoolDetailPage /></ProtectedRoute>
        } />
        <Route path="/admin/users" element={
          <ProtectedRoute allowedRoles={['platform_admin']}><UsersManagement /></ProtectedRoute>
        } />
        <Route path="/admin/users/:userId" element={
          <ProtectedRoute allowedRoles={['platform_admin']}><UserDetailsPage /></ProtectedRoute>
        } />
        <Route path="/admin/rules" element={
          <ProtectedRoute allowedRoles={['platform_admin']}><RulesManagementPage /></ProtectedRoute>
        } />
        <Route path="/admin/monitoring" element={
          <ProtectedRoute allowedRoles={['platform_admin']}><SystemMonitoringPage /></ProtectedRoute>
        } />
        <Route path="/admin/integrations" element={
          <ProtectedRoute allowedRoles={['platform_admin']}><IntegrationsPage /></ProtectedRoute>
        } />
        <Route path="/admin/security" element={
          <ProtectedRoute allowedRoles={['platform_admin']}><SecurityCenterPage /></ProtectedRoute>
        } />
        {/* Task #225 — IT §6.8 platform-admin hard-delete UI. */}
        <Route path="/admin/workspace-purge" element={
          <ProtectedRoute allowedRoles={['platform_admin']}><PlatformWorkspacePurgePage /></ProtectedRoute>
        } />
        <Route path="/admin/audit" element={
          <ProtectedRoute allowedRoles={['platform_admin', 'platform_security_officer', 'platform_data_analyst']}><AuditLogsPage /></ProtectedRoute>
        } />
        <Route path="/admin/communication" element={
          <ProtectedRoute allowedRoles={['platform_admin']}><CommunicationNotificationsPage /></ProtectedRoute>
        } />
        <Route path="/admin/product-hub" element={
          <ProtectedRoute allowedRoles={PRODUCT_HUB_ROLES}><ProductHubPage /></ProtectedRoute>
        } />
        <Route path="/admin/product-hub/submit" element={
          <ProtectedRoute allowedRoles={PRODUCT_HUB_ROLES}><ProductHubSubmitPage /></ProtectedRoute>
        } />
        <Route path="/admin/product-hub/issues/:issueId" element={
          <ProtectedRoute allowedRoles={PRODUCT_HUB_ROLES}><ProductHubIssuePage /></ProtectedRoute>
        } />
        {/* /notifications remains the standalone Notifications Center for non-school roles
            (teachers, parents, students). School roles see it consolidated inside the
            Communication Center at /principal/communication/notifications. */}
        <Route path="/notifications" element={
          <ProtectedRoute allowedRoles={ALL_AUTHENTICATED_ROLES}><NotificationsPage /></ProtectedRoute>
        } />
        <Route path="/settings" element={
          <ProtectedRoute allowedRoles={['platform_admin', 'school_principal']}><PlatformSettingsPage /></ProtectedRoute>
        } />

        {/* School Dashboard */}
        <Route path="/school" element={
          <ProtectedRoute allowedRoles={SCHOOL_ROLES}><SchoolDashboard /></ProtectedRoute>
        } />

        {/* Teacher Routes */}
        {/* Task #183 — Independent-Teacher first-login wizard. Allowed
            for IT only; the page itself bounces materialised users back
            to /teacher and non-IT roles to /dashboard. */}
        <Route path="/teacher/onboarding" element={
          <ProtectedRoute allowedRoles={['independent_teacher']}>
            <IndependentTeacherOnboardingWizard />
          </ProtectedRoute>
        } />
        <Route path="/teacher" element={
          <ProtectedRoute allowedRoles={TEACHER_ROLES}><TeacherResponsiveDashboard /></ProtectedRoute>
        } />
        <Route path="/teacher/home" element={
          <ProtectedRoute allowedRoles={TEACHER_ROLES}><TeacherHomePage /></ProtectedRoute>
        } />
        <Route path="/teacher/session/start" element={
          <ProtectedRoute allowedRoles={TEACHER_ROLES}><SessionStartPage /></ProtectedRoute>
        } />
        <Route path="/teacher/session/teach" element={
          <ProtectedRoute allowedRoles={TEACHER_ROLES}><SessionTeachPage /></ProtectedRoute>
        } />
        {/* Standby Periods now lives as a tab inside the Classes page so all
            teaching surfaces share one shell. The legacy /teacher/standby
            route — and any in-app notifications still pointing at it — are
            redirected to the Classes page with the standby tab preselected.
            Backend remains the security boundary (`role == teacher`). */}
        <Route path="/teacher/standby" element={<Navigate to="/teacher/classes?tab=standby" replace />} />
        <Route path="/teacher/schedule" element={
          <ProtectedRoute allowedRoles={TEACHER_ROLES}><TeacherSchedulePage /></ProtectedRoute>
        } />
        <Route path="/teacher/classes" element={
          <ProtectedRoute allowedRoles={TEACHER_ROLES}><TeacherClassesPage /></ProtectedRoute>
        } />
        <Route path="/teacher/class/:classId" element={
          <ProtectedRoute allowedRoles={TEACHER_ROLES}><TeacherClassDetailPage /></ProtectedRoute>
        } />
        <Route path="/teacher/tasks" element={
          <ProtectedRoute allowedRoles={TEACHER_ROLES}><TeacherTasksPage /></ProtectedRoute>
        } />
        <Route path="/teacher/attendance" element={
          <ProtectedRoute allowedRoles={TEACHER_ROLES}><TeacherAttendanceManagePage /></ProtectedRoute>
        } />
        <Route path="/teacher/assessments" element={
          <ProtectedRoute allowedRoles={TEACHER_ROLES}><TeacherAssessmentsPage /></ProtectedRoute>
        } />
        <Route path="/teacher/behavior" element={
          <ProtectedRoute allowedRoles={TEACHER_ROLES}><TeacherBehaviorPage /></ProtectedRoute>
        } />
        <Route path="/teacher/students" element={
          <ProtectedRoute allowedRoles={TEACHER_ROLES}><TeacherStudentsPage /></ProtectedRoute>
        } />
        {/* Task #207 §6.1 — IT-only workspace-aware bulk student import.
            Backend gates /commit with require_recent_mfa_403; the global
            axios interceptor replays after passkey assertion. */}
        {/* Bulk import is gated by the backend `students.bulk_import_workspace`
            permission. The FE guard mirrors that contract via
            requiredPermission so a future rbac change that grants the
            permission to additional roles flows through automatically. */}
        <Route path="/teacher/import-students" element={
          <ProtectedRoute
            allowedRoles={['independent_teacher']}
            requiredPermission="students.bulk_import_workspace"
          ><ImportStudentsPage /></ProtectedRoute>
        } />
        {/* Task #278 — IT-only bulk import hub (students / classes /
            subjects / duplicate-week). Permission-gated on the new
            `classes.bulk_import_workspace` slice so the link only shows
            when the user has at least one of the new bulk capabilities. */}
        <Route path="/teacher/bulk-import" element={
          <ProtectedRoute
            allowedRoles={['independent_teacher']}
            requiredPermission="classes.bulk_import_workspace"
          ><BulkImportPage /></ProtectedRoute>
        } />
        <Route path="/teacher/sessions" element={<Navigate to="/teacher/classes?tab=sessions" replace />} />
        <Route path="/teacher/achievements" element={
          <ProtectedRoute allowedRoles={TEACHER_ROLES}><TeacherAchievementsPage /></ProtectedRoute>
        } />
        <Route path="/teacher/communication" element={
          <ProtectedRoute allowedRoles={TEACHER_ROLES}><TeacherCommunicationPage /></ProtectedRoute>
        } />
        <Route path="/teacher/resources" element={
          <ProtectedRoute allowedRoles={TEACHER_ROLES}><TeacherResourcesPage /></ProtectedRoute>
        } />
        {/* 2026-05-18 — Legacy teacher settings page consolidated
            into the canonical /account/settings hub. The redirect
            keeps historical bookmarks and any in-app links working.
            Role gate is preserved via ProtectedRoute. */}
        <Route path="/teacher/settings" element={
          <ProtectedRoute allowedRoles={TEACHER_ROLES}>
            <Navigate to="/account/settings" replace />
          </ProtectedRoute>
        } />
        {/* Task #189 §5.2 — Independent-Teacher only: reduced workspace
            settings page. Backend enforces a deny-by-default allow-list. */}
        <Route path="/teacher/workspace-settings" element={
          <ProtectedRoute allowedRoles={['independent_teacher']}><WorkspaceSettingsPage /></ProtectedRoute>
        } />
        {/* Task #193 §5.4 — Independent-Teacher only: manual schedule editor.
            Backend enforces IT role + workspace scope per-endpoint and uses
            optimistic concurrency on schedule_sessions.version. */}
        <Route path="/teacher/workspace-schedule" element={
          <ProtectedRoute allowedRoles={['independent_teacher']}><WorkspaceSchedulePage /></ProtectedRoute>
        } />
        {/* Task #208 §6.3 — Independent-Teacher only: personal calendar.
            Backend pins tenant_id=itw_{user_id} + created_by=user.id +
            is_personal=True on every read/write. */}
        <Route path="/teacher/calendar" element={
          <ProtectedRoute allowedRoles={['independent_teacher']}><TeacherPersonalCalendarPage /></ProtectedRoute>
        } />
        {/* Task #209 §6.4 — IT-only light AI lesson-planning assistant.
            2026-05-18: relocated into the "فصولي" tabs. The historical
            standalone route now redirects to the tab so bookmarks /
            external links keep working. The ProtectedRoute wrapper
            preserves the original `ai.lesson_plans` gate — users who
            lack the permission see the standard fallback before the
            redirect fires (matches the audit-log relocation pattern). */}
        <Route path="/teacher/lesson-planner" element={
          <ProtectedRoute
            allowedRoles={['independent_teacher']}
            requiredPermission="ai.lesson_plans"
          ><Navigate to="/teacher/classes?tab=lesson-planner" replace /></ProtectedRoute>
        } />
        {/* Task #190 §5.3 — Independent-Teacher only: workspace subjects
            CRUD. Backend pins school_id == itw_{user_id} on every write
            and returns 404 for cross-workspace ids per spec §8 inv. 3. */}
        <Route path="/teacher/subjects" element={
          <ProtectedRoute allowedRoles={['independent_teacher']}><TeacherSubjectsPage /></ProtectedRoute>
        } />
        {/* Task #248 — IT-only workspace audit-log view. Backend pins
            school_id == itw_{user_id} on every read, strips sensitive
            keys from details, and returns 404 for cross-workspace ids
            per spec §8 inv. 3. Read-only, no MFA step-up.

            2026-05-18: the page was relocated into Account Settings
            (tab id `activity`). We keep the route registered so it
            still permission-gates the destination, but the standalone
            page now mounts inside Settings via the deep-link redirect
            below — historical bookmarks land on the new tab without a
            broken-link experience. */}
        <Route path="/teacher/audit-log" element={
          <ProtectedRoute
            allowedRoles={['independent_teacher']}
            requiredPermission="audit.read_own_workspace"
          ><Navigate to="/account/settings#activity" replace /></ProtectedRoute>
        } />
        {/* Task #273 — IT-only workspace analytics dashboard. Backend
            pins tenant_id == itw_{user_id} on every aggregation and
            returns 404 for cross-workspace class_id (spec §8 inv. 3).
            Read-only; no MFA step-up. */}
        <Route path="/teacher/analytics" element={
          <ProtectedRoute
            allowedRoles={['independent_teacher']}
            requiredPermission="analytics.read_own_workspace"
          ><TeacherAnalyticsPage /></ProtectedRoute>
        } />
        {/* Task #249 — IT-only notifications inbox. */}
        {/* 2026-05-18 — IT Notifications Inbox merged into the
            unified "التواصل والإشعارات" hub. The historical
            standalone route now redirects to the hub's Inbox tab
            so existing bookmarks and email deep-links keep working.
            Role gate is preserved via ProtectedRoute. */}
        <Route path="/teacher/notifications" element={
          <ProtectedRoute allowedRoles={['independent_teacher']}>
            <Navigate to="/teacher/communication?tab=inbox" replace />
          </ProtectedRoute>
        } />
        {/* Student Portal Routes — TEMPORARILY DISABLED platform-wide while
            the student experience is being rebuilt. Backend rejects every
            student-role login/refresh/token-issuance attempt, so these pages
            can no longer be reached via a normal session. We redirect any
            deep-link to /login (instead of removing the routes entirely) so
            the portal can be reinstated without touching the router. The
            lazy-loaded StudentPortal modules above are intentionally left
            in place — disabling is reversible by reverting this block. */}
        <Route path="/student" element={<Navigate to="/login" replace />} />
        <Route path="/student/*" element={<Navigate to="/login" replace />} />

        {/* Parent Portal Routes */}
        <Route path="/parent" element={
          <ProtectedRoute allowedRoles={['parent']}><ParentPortalDashboard /></ProtectedRoute>
        } />
        {/* Unified Parent Student Profile hub. Old standalone child sub-routes
            below redirect into this single page with the matching active tab so
            existing notifications, bookmarks and deep links keep working. */}
        <Route path="/parent/children" element={
          <ProtectedRoute allowedRoles={['parent']}><ParentChildrenPage /></ProtectedRoute>
        } />
        <Route path="/parent/child/:childId" element={
          <ProtectedRoute allowedRoles={['parent']}>
            <ParentStudentTabRedirect tab="details" />
          </ProtectedRoute>
        } />
        <Route path="/parent/child/:childId/schedule" element={
          <ProtectedRoute allowedRoles={['parent']}>
            <ParentStudentTabRedirect tab="schedule" />
          </ProtectedRoute>
        } />
        <Route path="/parent/child/:childId/behaviour" element={
          <ProtectedRoute allowedRoles={['parent']}>
            <ParentStudentTabRedirect tab="behavior" />
          </ProtectedRoute>
        } />
        <Route path="/parent/child/:childId/homework" element={
          <ProtectedRoute allowedRoles={['parent']}>
            <ParentStudentTabRedirect tab="homework" />
          </ProtectedRoute>
        } />
        {/* Legacy standalone Reports page is consolidated into Student
            Profile (Reports & Statistics tab). Redirect any old links /
            notifications to the unified children hub so the parent can
            pick a child and view the in-profile reports tab. */}
        <Route path="/parent/reports" element={
          <ProtectedRoute allowedRoles={['parent']}><Navigate to="/parent/children" replace /></ProtectedRoute>
        } />
        <Route path="/parent/messages" element={
          <ProtectedRoute allowedRoles={['parent']}><ParentMessagesPage /></ProtectedRoute>
        } />
        {/* Absence Excuse is now a tab inside the Communication Center.
            Redirect old direct links so existing notifications/CTAs keep working. */}
        <Route path="/parent/absence-excuse" element={
          <Navigate to="/parent/communication?tab=excuses" replace />
        } />
        {/* Meeting Request is hidden from the parent UI for now but the route
            and component implementation are preserved for future reactivation. */}
        <Route path="/parent/meeting-request" element={
          <ProtectedRoute allowedRoles={['parent']}><ParentMeetingRequestPage /></ProtectedRoute>
        } />
        <Route path="/parent/settings" element={
          <ProtectedRoute allowedRoles={['parent']}><ParentSettingsPage /></ProtectedRoute>
        } />
        <Route path="/parent/legal/:docType" element={
          <ProtectedRoute allowedRoles={['parent']}><ParentLegalDocumentPage /></ProtectedRoute>
        } />
        <Route path="/parent/communication" element={
          <ProtectedRoute allowedRoles={['parent']}><ParentCommunicationCenter /></ProtectedRoute>
        } />
        {/* Legacy standalone student-profile route — collapsed into the
            unified /parent/children hub with the Details tab active. The
            old StudentProfilePage was removed; chips moved into a modal
            opened from /parent/children header. See spec
            2026-05-17-parent-single-student-profile-design.md. */}
        <Route path="/parent/child/:childId/profile" element={
          <ProtectedRoute allowedRoles={['parent']}>
            <ParentStudentTabRedirect tab="details" />
          </ProtectedRoute>
        } />
        <Route path="/parent/child/:childId/analytics" element={
          <ProtectedRoute allowedRoles={['parent']}><ParentStudentAnalyticsPage /></ProtectedRoute>
        } />

        {/* Principal Dashboard */}
        <Route path="/principal" element={
          <ProtectedRoute allowedRoles={['school_principal', 'school_admin']}><PrincipalDashboard /></ProtectedRoute>
        } />
        <Route path="/principal/communication" element={
          <ProtectedRoute allowedRoles={SCHOOL_ROLES}><CommunicationCenterPage /></ProtectedRoute>
        } />
        <Route path="/principal/communication/notifications" element={
          <ProtectedRoute allowedRoles={SCHOOL_ROLES}><CommunicationCenterPage /></ProtectedRoute>
        } />

        {/* School Management Routes (attendance, assessments, users, classes, subjects) */}
        <Route path="/admin/attendance" element={
          <ProtectedRoute allowedRoles={SCHOOL_TEACHING_ROLES}><AttendancePage /></ProtectedRoute>
        } />
        <Route path="/principal/users-management" element={
          <ProtectedRoute allowedRoles={SCHOOL_ROLES}><UsersClassesManagement /></ProtectedRoute>
        } />
        {/* TEMPORARILY HIDDEN — Exams & Assessments module under maintenance.
            Restore by uncommenting the route below and removing the redirect.
        <Route path="/admin/assessments" element={
          <ProtectedRoute allowedRoles={SCHOOL_TEACHING_ROLES}><AssessmentPage /></ProtectedRoute>
        } />
        */}
        <Route path="/admin/assessments" element={<Navigate to="/dashboard" replace />} />
        <Route path="/admin/users-management" element={
          <ProtectedRoute allowedRoles={SCHOOL_ROLES}><UsersClassesManagement /></ProtectedRoute>
        } />
        <Route path="/admin/teachers" element={
          <ProtectedRoute allowedRoles={SCHOOL_ROLES}><UsersClassesManagement /></ProtectedRoute>
        } />
        <Route path="/admin/students" element={
          <ProtectedRoute allowedRoles={SCHOOL_ROLES}><StudentsPage /></ProtectedRoute>
        } />
        <Route path="/admin/classes" element={
          <ProtectedRoute allowedRoles={SCHOOL_ROLES}><ClassesPage /></ProtectedRoute>
        } />
        <Route path="/admin/classes/:classId" element={
          <ProtectedRoute allowedRoles={SCHOOL_ROLES}><ClassDetailPage /></ProtectedRoute>
        } />
        <Route path="/principal/classes/:classId" element={
          <ProtectedRoute allowedRoles={SCHOOL_ROLES}><ClassDetailPage /></ProtectedRoute>
        } />
        <Route path="/admin/students/:studentId" element={
          <ProtectedRoute allowedRoles={SCHOOL_ROLES}><AdminStudentProfilePage /></ProtectedRoute>
        } />
        <Route path="/principal/students/:studentId" element={
          <ProtectedRoute allowedRoles={SCHOOL_ROLES}><AdminStudentProfilePage /></ProtectedRoute>
        } />
        <Route path="/admin/subjects" element={
          <ProtectedRoute allowedRoles={SCHOOL_ROLES}><SubjectsPage /></ProtectedRoute>
        } />

        {/* School-prefixed aliases for principal-facing navigation (used by readiness panel fix links) */}
        <Route path="/school/classes" element={
          <ProtectedRoute allowedRoles={SCHOOL_ROLES}><ClassesPage /></ProtectedRoute>
        } />
        <Route path="/school/classes/:classId" element={
          <ProtectedRoute allowedRoles={SCHOOL_ROLES}><ClassDetailPage /></ProtectedRoute>
        } />
        <Route path="/school/subjects" element={
          <ProtectedRoute allowedRoles={SCHOOL_ROLES}><SubjectsPage /></ProtectedRoute>
        } />
        <Route path="/school/teachers" element={
          <ProtectedRoute allowedRoles={SCHOOL_ROLES}><UsersClassesManagement /></ProtectedRoute>
        } />
        <Route path="/school/students" element={
          <ProtectedRoute allowedRoles={SCHOOL_ROLES}><StudentsPage /></ProtectedRoute>
        } />
        <Route path="/school/students/:studentId" element={
          <ProtectedRoute allowedRoles={SCHOOL_ROLES}><AdminStudentProfilePage /></ProtectedRoute>
        } />
        <Route path="/academic-structure" element={<Navigate to="/school/settings?section=academic" replace />} />

        {/* Scheduling */}
        <Route path="/admin/schedule" element={
          <ProtectedRoute allowedRoles={SCHOOL_ROLES}><SchedulePageNew /></ProtectedRoute>
        } />
        <Route path="/school/schedule" element={
          <ProtectedRoute allowedRoles={SCHOOL_ROLES}><SchedulePageNew /></ProtectedRoute>
        } />
        <Route path="/school/standby" element={
          <ProtectedRoute allowedRoles={SCHOOL_ROLES}><StandbyRosterPage /></ProtectedRoute>
        } />
        <Route path="/admin/standby" element={
          <ProtectedRoute allowedRoles={SCHOOL_ROLES}><StandbyRosterPage /></ProtectedRoute>
        } />
        <Route path="/admin/time-slots" element={
          <ProtectedRoute allowedRoles={SCHOOL_ROLES}><TimeSlotsPage /></ProtectedRoute>
        } />
        <Route path="/admin/teacher-assignments" element={
          <ProtectedRoute allowedRoles={SCHOOL_ROLES}><TeacherAssignmentsPage /></ProtectedRoute>
        } />
        <Route path="/admin/teacher-attendance" element={
          <ProtectedRoute allowedRoles={SCHOOL_ROLES}><TeacherAttendancePage /></ProtectedRoute>
        } />

        {/* School Principal Settings & Reports */}
        <Route path="/principal/settings" element={
          <ProtectedRoute allowedRoles={SCHOOL_PRINCIPAL_ROLES}><SchoolSettingsPagePro /></ProtectedRoute>
        } />
        <Route path="/school/settings" element={
          <ProtectedRoute allowedRoles={SCHOOL_PRINCIPAL_ROLES}><SchoolSettingsPagePro /></ProtectedRoute>
        } />
        <Route path="/school/academic-structure" element={<Navigate to="/school/settings?section=academic" replace />} />
        <Route path="/principal/academic-structure" element={<Navigate to="/school/settings?section=academic" replace />} />
        <Route path="/principal/timetable" element={<Navigate to="/school/schedule" replace />} />
        <Route path="/school/teacher-class-assignments" element={
          <ProtectedRoute allowedRoles={SCHOOL_ROLES}><TeacherClassAssignmentPage /></ProtectedRoute>
        } />
        <Route path="/principal/ai-insights" element={
          <ProtectedRoute allowedRoles={[...SCHOOL_ROLES, 'platform_admin', 'teacher']}><AIInsightsPage /></ProtectedRoute>
        } />
        <Route path="/ai-insights" element={
          <ProtectedRoute allowedRoles={[...SCHOOL_ROLES, 'platform_admin', 'teacher']}><AIInsightsPage /></ProtectedRoute>
        } />

        {/* Account Settings - All authenticated users */}
        <Route path="/account/settings" element={
          <ProtectedRoute allowedRoles={ALL_AUTHENTICATED_ROLES}><AccountSettingsPage /></ProtectedRoute>
        } />

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
