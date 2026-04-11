import { Routes, Route, Navigate } from "react-router-dom";
import { ProtectedRoute, PublicRoute } from "../components/guards/RouteGuards";

import { LandingPage } from "../pages/LandingPage";
import { LoginPage } from "../pages/LoginPage";
import { RegisterPage } from "../pages/RegisterPage";
import { TeacherSelfRegistration } from "../pages/TeacherSelfRegistration";
import { AdminDashboard } from "../pages/AdminDashboard";
import { SchoolDashboard } from "../pages/SchoolDashboard";
import TeacherDashboard from "../pages/TeacherDashboard";
import StudentDashboard from "../pages/StudentDashboard";
import ParentDashboard from "../pages/ParentDashboard";
import PrincipalDashboard from "../pages/PrincipalDashboard";
import { TeachersPage } from "../pages/TeachersPage";
import UsersClassesManagement from "../pages/UsersClassesManagement";
import ClassDetailPage from "../pages/ClassDetailPage";
import AdminStudentProfilePage from "../pages/StudentProfilePage";
import { StudentsPage } from "../pages/StudentsPage";
import { ClassesPage } from "../pages/ClassesPage";
import { SubjectsPage } from "../pages/SubjectsPage";
import SchedulePageNew from "../pages/SchedulePageNew";
import { PrincipalTimetablePage } from "../components/timetable";
import { TimeSlotsPage } from "../pages/TimeSlotsPage";
import { TeacherAssignmentsPage } from "../pages/TeacherAssignmentsPage";
import { AttendancePage } from "../pages/AttendancePage";
import { TeacherAttendancePage } from "../pages/TeacherAttendancePage";
import { AssessmentPage } from "../pages/AssessmentPage";
import { NotificationsPage } from "../pages/NotificationsPage";

import {
  TeacherHomePage,
  TeacherMainDashboard,
  TeacherResponsiveDashboard,
  SessionStartPage,
  SessionTeachPage,
  TeacherSchedulePage,
  TeacherClassesPage,
  TeacherClassDetailPage,
  TeacherTasksPage,
  TeacherAttendanceManagePage,
  TeacherAssessmentsPage,
  TeacherBehaviorPage,
  TeacherStudentsPage,
  TeacherAchievementsPage,
  TeacherCommunicationPage,
  TeacherResourcesPage,
  TeacherSettingsPage
} from "../pages/TeacherModule";

import { ProductHubPage } from "../pages/ProductHubPage";
import { ProductHubSubmitPage } from "../pages/ProductHubSubmitPage";
import { ProductHubIssuePage } from "../pages/ProductHubIssuePage";

import { PlatformSchoolsPage } from "../pages/PlatformSchoolsPage";
import PlatformSchoolDetailPage from "../pages/PlatformSchoolDetailPage";
import { PlatformUsersPage } from "../pages/PlatformUsersPage";
import { PlatformNotificationsPage } from "../pages/PlatformNotificationsPage";
import { PlatformSettingsPage } from "../pages/PlatformSettingsPage";
import { RulesManagementPage } from "../pages/RulesManagementPage";
import { SystemMonitoringPage } from "../pages/SystemMonitoringPage";
import IntegrationsPage from "../pages/IntegrationsPage";
import SecurityCenterPage from "../pages/SecurityCenterPage";
import { CommunicationNotificationsPage } from "../pages/CommunicationNotificationsPage";
import { CommunicationCenterPage } from "../pages/CommunicationCenterPage";
import TenantsManagement from "../pages/TenantsManagement";
import TeacherClassAssignmentPage from "../pages/TeacherClassAssignmentPage";

import SchoolSettingsPagePro from "../pages/SchoolSettingsPagePro";
import { AIInsightsPage } from "../pages/AIInsightsPage";
import { AccountSettingsPage } from "../pages/AccountSettingsPage";
import ForcePasswordChange from "../pages/ForcePasswordChange";
import RegistrationConfirmationPage from "../pages/RegistrationConfirmationPage";
import UsersManagement from "../pages/UsersManagement";
import UserDetailsPage from "../pages/UserDetailsPage";
import AuditLogsPage from "../pages/AuditLogsPage";

import {
  StudentPortalDashboard,
  StudentSchedulePage,
  StudentGradesPage,
  StudentAttendancePage,
  StudentProfilePage,
  StudentProgressPage,
  StudentAchievementsPage
} from "../pages/StudentPortal";

import {
  ParentPortalDashboard,
  ChildDetailsPage,
  ChildSchedulePage,
  ParentChildrenPage,
  ChildBehaviorPage,
  ChildHomeworkPage,
  ParentReportsPage,
  ParentMessagesPage,
  ParentAbsenceExcusePage,
  ParentMeetingRequestPage,
  ParentSettingsPage,
  ParentCommunicationCenter,
  StudentProfilePage as ParentStudentProfilePage,
  StudentAnalyticsPage as ParentStudentAnalyticsPage
} from "../pages/ParentPortal";

const SCHOOL_ROLES = ['school_principal', 'school_admin', 'school_sub_admin'];
const SCHOOL_TEACHING_ROLES = [...SCHOOL_ROLES, 'teacher'];
const ALL_AUTHENTICATED_ROLES = ['platform_admin', ...SCHOOL_ROLES, 'teacher', 'student', 'parent'];
const PRODUCT_HUB_ROLES = ['platform_admin', 'platform_operations_manager', 'school_principal', 'school_admin', 'teacher'];

export default function AppRoutes() {
  return (
    <Routes>
      {/* Public Routes */}
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
      <Route path="/register" element={<PublicRoute><RegisterPage /></PublicRoute>} />
      <Route path="/registration-confirmation" element={<RegistrationConfirmationPage />} />
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
        <ProtectedRoute allowedRoles={['teacher']}><TeacherResponsiveDashboard /></ProtectedRoute>
      } />
      <Route path="/teacher/home" element={
        <ProtectedRoute allowedRoles={['teacher']}><TeacherHomePage /></ProtectedRoute>
      } />
      <Route path="/teacher/session/start" element={
        <ProtectedRoute allowedRoles={['teacher']}><SessionStartPage /></ProtectedRoute>
      } />
      <Route path="/teacher/session/teach" element={
        <ProtectedRoute allowedRoles={['teacher']}><SessionTeachPage /></ProtectedRoute>
      } />
      <Route path="/teacher/schedule" element={
        <ProtectedRoute allowedRoles={['teacher']}><TeacherSchedulePage /></ProtectedRoute>
      } />
      <Route path="/teacher/classes" element={
        <ProtectedRoute allowedRoles={['teacher']}><TeacherClassesPage /></ProtectedRoute>
      } />
      <Route path="/teacher/class/:classId" element={
        <ProtectedRoute allowedRoles={['teacher']}><TeacherClassDetailPage /></ProtectedRoute>
      } />
      <Route path="/teacher/tasks" element={
        <ProtectedRoute allowedRoles={['teacher']}><TeacherTasksPage /></ProtectedRoute>
      } />
      <Route path="/teacher/attendance" element={
        <ProtectedRoute allowedRoles={['teacher']}><TeacherAttendanceManagePage /></ProtectedRoute>
      } />
      <Route path="/teacher/assessments" element={
        <ProtectedRoute allowedRoles={['teacher']}><TeacherAssessmentsPage /></ProtectedRoute>
      } />
      <Route path="/teacher/behavior" element={
        <ProtectedRoute allowedRoles={['teacher']}><TeacherBehaviorPage /></ProtectedRoute>
      } />
      <Route path="/teacher/students" element={
        <ProtectedRoute allowedRoles={['teacher']}><TeacherStudentsPage /></ProtectedRoute>
      } />
      <Route path="/teacher/sessions" element={<Navigate to="/teacher/classes?tab=sessions" replace />} />
      <Route path="/teacher/achievements" element={
        <ProtectedRoute allowedRoles={['teacher']}><TeacherAchievementsPage /></ProtectedRoute>
      } />
      <Route path="/teacher/communication" element={
        <ProtectedRoute allowedRoles={['teacher']}><TeacherCommunicationPage /></ProtectedRoute>
      } />
      <Route path="/teacher/resources" element={
        <ProtectedRoute allowedRoles={['teacher']}><TeacherResourcesPage /></ProtectedRoute>
      } />
      <Route path="/teacher/settings" element={
        <ProtectedRoute allowedRoles={['teacher']}><TeacherSettingsPage /></ProtectedRoute>
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

      {/* School Management Routes (attendance, assessments, users, classes, subjects) */}
      <Route path="/admin/attendance" element={
        <ProtectedRoute allowedRoles={SCHOOL_TEACHING_ROLES}><AttendancePage /></ProtectedRoute>
      } />
      <Route path="/principal/users-management" element={
        <ProtectedRoute allowedRoles={SCHOOL_ROLES}><UsersClassesManagement /></ProtectedRoute>
      } />
      <Route path="/admin/assessments" element={
        <ProtectedRoute allowedRoles={SCHOOL_TEACHING_ROLES}><AssessmentPage /></ProtectedRoute>
      } />
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

      {/* Scheduling */}
      <Route path="/admin/schedule" element={
        <ProtectedRoute allowedRoles={SCHOOL_ROLES}><SchedulePageNew /></ProtectedRoute>
      } />
      <Route path="/school/schedule" element={
        <ProtectedRoute allowedRoles={SCHOOL_ROLES}><SchedulePageNew /></ProtectedRoute>
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
        <ProtectedRoute allowedRoles={SCHOOL_ROLES}><SchoolSettingsPagePro /></ProtectedRoute>
      } />
      <Route path="/school/settings" element={
        <ProtectedRoute allowedRoles={SCHOOL_ROLES}><SchoolSettingsPagePro /></ProtectedRoute>
      } />
      <Route path="/school/academic-structure" element={<Navigate to="/school/settings?section=academic" replace />} />
      <Route path="/principal/academic-structure" element={<Navigate to="/school/settings?section=academic" replace />} />
      <Route path="/principal/timetable" element={
        <ProtectedRoute allowedRoles={SCHOOL_ROLES}><PrincipalTimetablePage /></ProtectedRoute>
      } />
      <Route path="/school/teacher-class-assignments" element={
        <ProtectedRoute allowedRoles={SCHOOL_ROLES}><TeacherClassAssignmentPage /></ProtectedRoute>
      } />
      <Route path="/principal/ai-insights" element={
        <ProtectedRoute allowedRoles={[...SCHOOL_ROLES, 'platform_admin', 'teacher']}><AIInsightsPage /></ProtectedRoute>
      } />

      {/* Account Settings - All authenticated users */}
      <Route path="/account/settings" element={
        <ProtectedRoute allowedRoles={ALL_AUTHENTICATED_ROLES}><AccountSettingsPage /></ProtectedRoute>
      } />

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
