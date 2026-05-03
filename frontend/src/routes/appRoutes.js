import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { ProtectedRoute, PublicRoute } from "../components/guards/RouteGuards";

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
const TeacherAchievementsPage = lazy(() => import("../pages/TeacherModule").then(m => ({ default: m.TeacherAchievementsPage })));
const TeacherCommunicationPage = lazy(() => import("../pages/TeacherModule").then(m => ({ default: m.TeacherCommunicationPage })));
const TeacherResourcesPage = lazy(() => import("../pages/TeacherModule").then(m => ({ default: m.TeacherResourcesPage })));
const TeacherSettingsPage = lazy(() => import("../pages/TeacherModule").then(m => ({ default: m.TeacherSettingsPage })));

const ProductHubPage = lazy(() => import("../pages/ProductHubPage").then(m => ({ default: m.ProductHubPage })));
const ProductHubSubmitPage = lazy(() => import("../pages/ProductHubSubmitPage").then(m => ({ default: m.ProductHubSubmitPage })));
const ProductHubIssuePage = lazy(() => import("../pages/ProductHubIssuePage").then(m => ({ default: m.ProductHubIssuePage })));

const PlatformSchoolsPage = lazy(() => import("../pages/PlatformSchoolsPage").then(m => ({ default: m.PlatformSchoolsPage })));
const PlatformSchoolDetailPage = lazy(() => import("../pages/PlatformSchoolDetailPage"));
const PlatformUsersPage = lazy(() => import("../pages/PlatformUsersPage").then(m => ({ default: m.PlatformUsersPage })));
const PlatformNotificationsPage = lazy(() => import("../pages/PlatformNotificationsPage").then(m => ({ default: m.PlatformNotificationsPage })));
const PlatformSettingsPage = lazy(() => import("../pages/PlatformSettingsPage").then(m => ({ default: m.PlatformSettingsPage })));
const RulesManagementPage = lazy(() => import("../pages/RulesManagementPage").then(m => ({ default: m.RulesManagementPage })));
// Heavy: SystemMonitoringPage pulls recharts
const SystemMonitoringPage = lazy(() => import("../pages/SystemMonitoringPage").then(m => ({ default: m.SystemMonitoringPage })));
const IntegrationsPage = lazy(() => import("../pages/IntegrationsPage"));
// Heavy: SecurityCenterPage already dynamic-imports jspdf+html2canvas at click time
const SecurityCenterPage = lazy(() => import("../pages/SecurityCenterPage"));
const CommunicationNotificationsPage = lazy(() => import("../pages/CommunicationNotificationsPage").then(m => ({ default: m.CommunicationNotificationsPage })));
const CommunicationCenterPage = lazy(() => import("../pages/CommunicationCenterPage").then(m => ({ default: m.CommunicationCenterPage })));
const TenantsManagement = lazy(() => import("../pages/TenantsManagement"));
const TeacherClassAssignmentPage = lazy(() => import("../pages/TeacherClassAssignmentPage"));

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
const ParentReportsPage = lazy(() => import("../pages/ParentPortal").then(m => ({ default: m.ParentReportsPage })));
const ParentMessagesPage = lazy(() => import("../pages/ParentPortal").then(m => ({ default: m.ParentMessagesPage })));
const ParentAbsenceExcusePage = lazy(() => import("../pages/ParentPortal").then(m => ({ default: m.ParentAbsenceExcusePage })));
const ParentMeetingRequestPage = lazy(() => import("../pages/ParentPortal").then(m => ({ default: m.ParentMeetingRequestPage })));
const ParentSettingsPage = lazy(() => import("../pages/ParentPortal").then(m => ({ default: m.ParentSettingsPage })));
const ParentCommunicationCenter = lazy(() => import("../pages/ParentPortal").then(m => ({ default: m.ParentCommunicationCenter })));
const ParentStudentProfilePage = lazy(() => import("../pages/ParentPortal").then(m => ({ default: m.StudentProfilePage })));
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
        <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
        <Route path="/register" element={<PublicRoute><RegisterPage /></PublicRoute>} />
        <Route path="/registration-confirmation" element={<RegistrationConfirmationPage />} />
        <Route path="/forgot-password" element={<PublicRoute><ForgotPasswordPage /></PublicRoute>} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/teacher-register" element={<TeacherSelfRegistration />} />

        {/* Force Password Change */}
        <Route path="/change-password" element={
          <ProtectedRoute skipPasswordCheck={true}><ForcePasswordChange /></ProtectedRoute>
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
        <Route path="/teacher/settings" element={
          <ProtectedRoute allowedRoles={TEACHER_ROLES}><TeacherSettingsPage /></ProtectedRoute>
        } />

        {/* Student Portal Routes */}
        <Route path="/student" element={
          <ProtectedRoute allowedRoles={['student']}><StudentPortalDashboard /></ProtectedRoute>
        } />
        <Route path="/student/schedule" element={
          <ProtectedRoute allowedRoles={['student']}><StudentSchedulePage /></ProtectedRoute>
        } />
        <Route path="/student/grades" element={
          <ProtectedRoute allowedRoles={['student']}><StudentGradesPage /></ProtectedRoute>
        } />
        <Route path="/student/attendance" element={
          <ProtectedRoute allowedRoles={['student']}><StudentAttendancePage /></ProtectedRoute>
        } />
        <Route path="/student/profile" element={
          <ProtectedRoute allowedRoles={['student']}><StudentProfilePage /></ProtectedRoute>
        } />
        <Route path="/student/progress" element={
          <ProtectedRoute allowedRoles={['student']}><StudentProgressPage /></ProtectedRoute>
        } />
        <Route path="/student/achievements" element={
          <ProtectedRoute allowedRoles={['student']}><StudentAchievementsPage /></ProtectedRoute>
        } />

        {/* Parent Portal Routes */}
        <Route path="/parent" element={
          <ProtectedRoute allowedRoles={['parent']}><ParentPortalDashboard /></ProtectedRoute>
        } />
        <Route path="/parent/child/:childId" element={
          <ProtectedRoute allowedRoles={['parent']}><ChildDetailsPage /></ProtectedRoute>
        } />
        <Route path="/parent/child/:childId/schedule" element={
          <ProtectedRoute allowedRoles={['parent']}><ChildSchedulePage /></ProtectedRoute>
        } />
        <Route path="/parent/children" element={
          <ProtectedRoute allowedRoles={['parent']}><ParentChildrenPage /></ProtectedRoute>
        } />
        <Route path="/parent/child/:childId/behaviour" element={
          <ProtectedRoute allowedRoles={['parent']}><ChildBehaviorPage /></ProtectedRoute>
        } />
        <Route path="/parent/child/:childId/homework" element={
          <ProtectedRoute allowedRoles={['parent']}><ChildHomeworkPage /></ProtectedRoute>
        } />
        <Route path="/parent/reports" element={
          <ProtectedRoute allowedRoles={['parent']}><ParentReportsPage /></ProtectedRoute>
        } />
        <Route path="/parent/messages" element={
          <ProtectedRoute allowedRoles={['parent']}><ParentMessagesPage /></ProtectedRoute>
        } />
        <Route path="/parent/absence-excuse" element={
          <ProtectedRoute allowedRoles={['parent']}><ParentAbsenceExcusePage /></ProtectedRoute>
        } />
        <Route path="/parent/meeting-request" element={
          <ProtectedRoute allowedRoles={['parent']}><ParentMeetingRequestPage /></ProtectedRoute>
        } />
        <Route path="/parent/settings" element={
          <ProtectedRoute allowedRoles={['parent']}><ParentSettingsPage /></ProtectedRoute>
        } />
        <Route path="/parent/communication" element={
          <ProtectedRoute allowedRoles={['parent']}><ParentCommunicationCenter /></ProtectedRoute>
        } />
        <Route path="/parent/child/:childId/profile" element={
          <ProtectedRoute allowedRoles={['parent']}><ParentStudentProfilePage /></ProtectedRoute>
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
