import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { ThemeProvider } from "./contexts/ThemeContext";
import { WebSocketProvider } from "./contexts/WebSocketContext";
import { NassaqAlertProvider } from "./components/ui/NassaqAlertDialog";
import ErrorBoundary from "./components/ErrorBoundary";

// Pages
import { LandingPage } from "./pages/LandingPage";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { TeacherSelfRegistration } from "./pages/TeacherSelfRegistration";
import { AdminDashboard } from "./pages/AdminDashboard";
import { SchoolDashboard } from "./pages/SchoolDashboard";
import TeacherDashboard from "./pages/TeacherDashboard";
import StudentDashboard from "./pages/StudentDashboard";
import ParentDashboard from "./pages/ParentDashboard";
import PrincipalDashboard from "./pages/PrincipalDashboard";
import { TeachersPage } from "./pages/TeachersPage";
import UsersClassesManagement from "./pages/UsersClassesManagement";
import ClassDetailPage from "./pages/ClassDetailPage";
import AdminStudentProfilePage from "./pages/StudentProfilePage";
import { StudentsPage } from "./pages/StudentsPage";
import { ClassesPage } from "./pages/ClassesPage";
import { SubjectsPage } from "./pages/SubjectsPage";
import SchedulePageNew from "./pages/SchedulePageNew";
// SmartTimetablePage removed - functionality merged into SchedulePageNew
// New Timetable Page Component
import { PrincipalTimetablePage } from "./components/timetable";
import { TimeSlotsPage } from "./pages/TimeSlotsPage";
import { TeacherAssignmentsPage } from "./pages/TeacherAssignmentsPage";
import { AttendancePage } from "./pages/AttendancePage";
import { TeacherAttendancePage } from "./pages/TeacherAttendancePage";
import { AssessmentPage } from "./pages/AssessmentPage";
import { NotificationsPage } from "./pages/NotificationsPage";

// Teacher Module Pages
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
  TeacherReportsPage,
  TeacherResourcesPage,
  TeacherSettingsPage
} from "./pages/TeacherModule";

// Platform Admin Pages
import { PlatformSchoolsPage } from "./pages/PlatformSchoolsPage";
import { PlatformUsersPage } from "./pages/PlatformUsersPage";
import { PlatformReportsPage } from "./pages/PlatformReportsPage";
import { PlatformNotificationsPage } from "./pages/PlatformNotificationsPage";
import { PlatformSettingsPage } from "./pages/PlatformSettingsPage";
import { RulesManagementPage } from "./pages/RulesManagementPage";
import { SystemMonitoringPage } from "./pages/SystemMonitoringPage";
import IntegrationsPage from "./pages/IntegrationsPage";
import SecurityCenterPage from "./pages/SecurityCenterPage";
import { CommunicationNotificationsPage } from "./pages/CommunicationNotificationsPage";
import { CommunicationCenterPage } from "./pages/CommunicationCenterPage";
// TeacherRequestsPage removed - now integrated in UsersManagement
import TenantsManagement from "./pages/TenantsManagement";
import TeacherClassAssignmentPage from "./pages/TeacherClassAssignmentPage";

// School Principal Pages
import SchoolSettingsPagePro from "./pages/SchoolSettingsPagePro";
import { SchoolReportsPage } from "./pages/SchoolReportsPage";
import { AIInsightsPage } from "./pages/AIInsightsPage";
import { AccountSettingsPage } from "./pages/AccountSettingsPage";
import ForcePasswordChange from "./pages/ForcePasswordChange";
import RegistrationConfirmationPage from "./pages/RegistrationConfirmationPage";
import UsersManagement from "./pages/UsersManagement";
import UserDetailsPage from "./pages/UserDetailsPage";
import { PlatformAnalyticsPage } from "./pages/PlatformAnalyticsPage";
import AuditLogsPage from "./pages/AuditLogsPage";

// Student Portal Pages
import {
  StudentPortalDashboard,
  StudentSchedulePage,
  StudentGradesPage,
  StudentAttendancePage,
  StudentProfilePage,
  StudentProgressPage,
  StudentAchievementsPage
} from "./pages/StudentPortal";

// Parent Portal Pages
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
  ParentSettingsPage
} from "./pages/ParentPortal";

// Protected Route Component
const ProtectedRoute = ({ children, allowedRoles, skipPasswordCheck = false }) => {
  const { user, loading, isAuthenticated, isImpersonating, getEffectiveRole } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-brand-navy">جاري التحميل...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // Check if user must change password (skip for password change page itself)
  if (!skipPasswordCheck && user?.must_change_password) {
    return <Navigate to="/change-password" replace />;
  }
  
  // Get effective role (supports impersonation)
  const effectiveRole = getEffectiveRole ? getEffectiveRole() : user?.role;

  if (allowedRoles && !allowedRoles.includes(effectiveRole)) {
    // Redirect to appropriate dashboard based on effective role
    switch (effectiveRole) {
      case 'platform_admin':
        return <Navigate to="/admin" replace />;
      case 'school_principal':
        return <Navigate to="/principal" replace />;
      case 'school_sub_admin':
        return <Navigate to="/school" replace />;
      case 'school_admin':
        return <Navigate to="/principal" replace />;
      case 'platform_operations_manager':
        return <Navigate to="/admin" replace />;
      case 'teacher':
        return <Navigate to="/teacher" replace />;
      case 'student':
        return <Navigate to="/student" replace />;
      case 'parent':
        return <Navigate to="/parent" replace />;
      default:
        return <Navigate to="/" replace />;
    }
  }

  return children;
};

// Public Route (redirect if already logged in)
const PublicRoute = ({ children }) => {
  const { user, loading, isAuthenticated } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-brand-navy">جاري التحميل...</div>
      </div>
    );
  }

  if (isAuthenticated) {
    // Redirect to appropriate dashboard based on role
    switch (user?.role) {
      case 'platform_admin':
        return <Navigate to="/admin" replace />;
      case 'school_principal':
        return <Navigate to="/principal" replace />;
      case 'school_sub_admin':
        return <Navigate to="/school" replace />;
      case 'school_admin':
        return <Navigate to="/principal" replace />;
      case 'platform_operations_manager':
        return <Navigate to="/admin" replace />;
      case 'teacher':
        return <Navigate to="/teacher" replace />;
      case 'student':
        return <Navigate to="/student" replace />;
      case 'parent':
        return <Navigate to="/parent" replace />;
      default:
        return <Navigate to="/" replace />;
    }
  }

  return children;
};

function AppRoutes() {
  return (
    <Routes>
      {/* Public Routes */}
      <Route path="/" element={<LandingPage />} />
      <Route
        path="/login"
        element={
          <PublicRoute>
            <LoginPage />
          </PublicRoute>
        }
      />
      <Route
        path="/register"
        element={
          <PublicRoute>
            <RegisterPage />
          </PublicRoute>
        }
      />
      <Route
        path="/registration-confirmation"
        element={<RegistrationConfirmationPage />}
      />
      <Route
        path="/teacher-register"
        element={<TeacherSelfRegistration />}
      />

      {/* Force Password Change Route */}
      <Route
        path="/change-password"
        element={
          <ProtectedRoute skipPasswordCheck={true}>
            <ForcePasswordChange />
          </ProtectedRoute>
        }
      />

      {/* Platform Admin Routes */}
      <Route
        path="/admin"
        element={
          <ProtectedRoute allowedRoles={['platform_admin', 'platform_operations_manager']}>
            <AdminDashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/schools"
        element={
          <ProtectedRoute allowedRoles={['platform_admin']}>
            <TenantsManagement />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/tenants"
        element={
          <ProtectedRoute allowedRoles={['platform_admin']}>
            <TenantsManagement />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/schools-table"
        element={
          <ProtectedRoute allowedRoles={['platform_admin']}>
            <PlatformSchoolsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/users"
        element={
          <ProtectedRoute allowedRoles={['platform_admin']}>
            <UsersManagement />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/users/:userId"
        element={
          <ProtectedRoute allowedRoles={['platform_admin']}>
            <UserDetailsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/users-old"
        element={
          <ProtectedRoute allowedRoles={['platform_admin']}>
            <PlatformUsersPage />
          </ProtectedRoute>
        }
      />
      {/* Teacher Requests page removed - functionality merged into UsersManagement */}
      <Route
        path="/admin/rules"
        element={
          <ProtectedRoute allowedRoles={['platform_admin']}>
            <RulesManagementPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/monitoring"
        element={
          <ProtectedRoute allowedRoles={['platform_admin']}>
            <SystemMonitoringPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/integrations"
        element={
          <ProtectedRoute allowedRoles={['platform_admin']}>
            <IntegrationsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/security"
        element={
          <ProtectedRoute allowedRoles={['platform_admin']}>
            <SecurityCenterPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/audit"
        element={
          <ProtectedRoute allowedRoles={['platform_admin', 'platform_security_officer', 'platform_data_analyst']}>
            <AuditLogsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/communication"
        element={
          <ProtectedRoute allowedRoles={['platform_admin']}>
            <CommunicationNotificationsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/analytics"
        element={
          <ProtectedRoute allowedRoles={['platform_admin']}>
            <PlatformAnalyticsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/reports"
        element={
          <ProtectedRoute allowedRoles={['platform_admin', 'ministry_rep']}>
            <PlatformReportsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/notifications"
        element={
          <ProtectedRoute allowedRoles={['platform_admin', 'school_principal', 'school_admin', 'school_sub_admin', 'teacher', 'student', 'parent']}>
            <NotificationsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings"
        element={
          <ProtectedRoute allowedRoles={['platform_admin', 'school_principal']}>
            <PlatformSettingsPage />
          </ProtectedRoute>
        }
      />

      {/* School Routes */}
      <Route
        path="/school"
        element={
          <ProtectedRoute allowedRoles={['school_principal', 'school_sub_admin', 'school_admin']}>
            <SchoolDashboard />
          </ProtectedRoute>
        }
      />
      
      {/* Teacher Dashboard Route - responsive: mobile shows TeacherHomePage, desktop shows TeacherMainDashboard */}
      <Route
        path="/teacher"
        element={
          <ProtectedRoute allowedRoles={['teacher']}>
            <TeacherResponsiveDashboard />
          </ProtectedRoute>
        }
      />
      
      {/* Teacher Mobile-First Home Page */}
      <Route
        path="/teacher/home"
        element={
          <ProtectedRoute allowedRoles={['teacher']}>
            <TeacherHomePage />
          </ProtectedRoute>
        }
      />
      
      {/* Teacher Session Routes */}
      <Route
        path="/teacher/session/start"
        element={
          <ProtectedRoute allowedRoles={['teacher']}>
            <SessionStartPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/teacher/session/teach"
        element={
          <ProtectedRoute allowedRoles={['teacher']}>
            <SessionTeachPage />
          </ProtectedRoute>
        }
      />
      
      {/* Teacher Module Routes */}
      <Route
        path="/teacher/schedule"
        element={
          <ProtectedRoute allowedRoles={['teacher']}>
            <TeacherSchedulePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/teacher/classes"
        element={
          <ProtectedRoute allowedRoles={['teacher']}>
            <TeacherClassesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/teacher/class/:classId"
        element={
          <ProtectedRoute allowedRoles={['teacher']}>
            <TeacherClassDetailPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/teacher/tasks"
        element={
          <ProtectedRoute allowedRoles={['teacher']}>
            <TeacherTasksPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/teacher/attendance"
        element={
          <ProtectedRoute allowedRoles={['teacher']}>
            <TeacherAttendanceManagePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/teacher/assessments"
        element={
          <ProtectedRoute allowedRoles={['teacher']}>
            <TeacherAssessmentsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/teacher/behavior"
        element={
          <ProtectedRoute allowedRoles={['teacher']}>
            <TeacherBehaviorPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/teacher/students"
        element={
          <ProtectedRoute allowedRoles={['teacher']}>
            <TeacherStudentsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/teacher/sessions"
        element={<Navigate to="/teacher/classes?tab=sessions" replace />}
      />
      <Route
        path="/teacher/achievements"
        element={
          <ProtectedRoute allowedRoles={['teacher']}>
            <TeacherAchievementsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/teacher/communication"
        element={
          <ProtectedRoute allowedRoles={['teacher']}>
            <TeacherCommunicationPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/teacher/reports"
        element={
          <ProtectedRoute allowedRoles={['teacher']}>
            <TeacherReportsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/teacher/resources"
        element={
          <ProtectedRoute allowedRoles={['teacher']}>
            <TeacherResourcesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/teacher/settings"
        element={
          <ProtectedRoute allowedRoles={['teacher']}>
            <TeacherSettingsPage />
          </ProtectedRoute>
        }
      />
      
      {/* Student Portal Routes */}
      <Route
        path="/student"
        element={
          <ProtectedRoute allowedRoles={['student']}>
            <StudentPortalDashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/student/schedule"
        element={
          <ProtectedRoute allowedRoles={['student']}>
            <StudentSchedulePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/student/grades"
        element={
          <ProtectedRoute allowedRoles={['student']}>
            <StudentGradesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/student/attendance"
        element={
          <ProtectedRoute allowedRoles={['student']}>
            <StudentAttendancePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/student/profile"
        element={
          <ProtectedRoute allowedRoles={['student']}>
            <StudentProfilePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/student/progress"
        element={
          <ProtectedRoute allowedRoles={['student']}>
            <StudentProgressPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/student/achievements"
        element={
          <ProtectedRoute allowedRoles={['student']}>
            <StudentAchievementsPage />
          </ProtectedRoute>
        }
      />
      
      {/* Parent Portal Routes */}
      <Route
        path="/parent"
        element={
          <ProtectedRoute allowedRoles={['parent']}>
            <ParentPortalDashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/parent/child/:childId"
        element={
          <ProtectedRoute allowedRoles={['parent']}>
            <ChildDetailsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/parent/child/:childId/schedule"
        element={
          <ProtectedRoute allowedRoles={['parent']}>
            <ChildSchedulePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/parent/children"
        element={
          <ProtectedRoute allowedRoles={['parent']}>
            <ParentChildrenPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/parent/child/:childId/behaviour"
        element={
          <ProtectedRoute allowedRoles={['parent']}>
            <ChildBehaviorPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/parent/child/:childId/homework"
        element={
          <ProtectedRoute allowedRoles={['parent']}>
            <ChildHomeworkPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/parent/reports"
        element={
          <ProtectedRoute allowedRoles={['parent']}>
            <ParentReportsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/parent/messages"
        element={
          <ProtectedRoute allowedRoles={['parent']}>
            <ParentMessagesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/parent/absence-excuse"
        element={
          <ProtectedRoute allowedRoles={['parent']}>
            <ParentAbsenceExcusePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/parent/meeting-request"
        element={
          <ProtectedRoute allowedRoles={['parent']}>
            <ParentMeetingRequestPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/parent/settings"
        element={
          <ProtectedRoute allowedRoles={['parent']}>
            <ParentSettingsPage />
          </ProtectedRoute>
        }
      />
      
      {/* Principal Dashboard Route */}
      <Route
        path="/principal"
        element={
          <ProtectedRoute allowedRoles={['school_principal', 'school_admin']}>
            <PrincipalDashboard />
          </ProtectedRoute>
        }
      />
      
      {/* Principal Communication Center - مركز التواصل والإشعارات لمدير المدرسة */}
      <Route
        path="/principal/communication"
        element={
          <ProtectedRoute allowedRoles={['school_principal', 'school_admin', 'school_sub_admin']}>
            <CommunicationCenterPage />
          </ProtectedRoute>
        }
      />
      
      {/* Attendance Route */}
      <Route
        path="/admin/attendance"
        element={
          <ProtectedRoute allowedRoles={['school_principal', 'school_admin', 'school_sub_admin', 'teacher']}>
            <AttendancePage />
          </ProtectedRoute>
        }
      />
      
      {/* Principal Users & Classes Management */}
      <Route
        path="/principal/users-management"
        element={
          <ProtectedRoute allowedRoles={['school_principal', 'school_admin', 'school_sub_admin']}>
            <UsersClassesManagement />
          </ProtectedRoute>
        }
      />
      
      {/* Assessment Route */}
      <Route
        path="/admin/assessments"
        element={
          <ProtectedRoute allowedRoles={['school_principal', 'school_admin', 'school_sub_admin', 'teacher']}>
            <AssessmentPage />
          </ProtectedRoute>
        }
      />

      {/* School Management Routes - Only for School Principal and Sub Admin (NOT Platform Admin) */}
      <Route
        path="/admin/users-management"
        element={
          <ProtectedRoute allowedRoles={['school_principal', 'school_admin', 'school_sub_admin']}>
            <UsersClassesManagement />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/teachers"
        element={
          <ProtectedRoute allowedRoles={['school_principal', 'school_admin', 'school_sub_admin']}>
            <UsersClassesManagement />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/students"
        element={
          <ProtectedRoute allowedRoles={['school_principal', 'school_admin', 'school_sub_admin']}>
            <StudentsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/classes"
        element={
          <ProtectedRoute allowedRoles={['school_principal', 'school_admin', 'school_sub_admin']}>
            <ClassesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/classes/:classId"
        element={
          <ProtectedRoute allowedRoles={['school_principal', 'school_admin', 'school_sub_admin']}>
            <ClassDetailPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/principal/classes/:classId"
        element={
          <ProtectedRoute allowedRoles={['school_principal', 'school_admin', 'school_sub_admin']}>
            <ClassDetailPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/students/:studentId"
        element={
          <ProtectedRoute allowedRoles={['school_principal', 'school_admin', 'school_sub_admin']}>
            <AdminStudentProfilePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/principal/students/:studentId"
        element={
          <ProtectedRoute allowedRoles={['school_principal', 'school_admin', 'school_sub_admin']}>
            <AdminStudentProfilePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/subjects"
        element={
          <ProtectedRoute allowedRoles={['school_principal', 'school_admin', 'school_sub_admin']}>
            <SubjectsPage />
          </ProtectedRoute>
        }
      />
      
      {/* Scheduling Routes - Only for School Principal and Sub Admin (NOT Platform Admin) */}
      <Route
        path="/admin/schedule"
        element={
          <ProtectedRoute allowedRoles={['school_principal', 'school_admin', 'school_sub_admin']}>
            <SchedulePageNew />
          </ProtectedRoute>
        }
      />
      <Route
        path="/school/schedule"
        element={
          <ProtectedRoute allowedRoles={['school_principal', 'school_admin', 'school_sub_admin']}>
            <SchedulePageNew />
          </ProtectedRoute>
        }
      />
      {/* SmartTimetablePage routes removed - functionality merged into SchedulePageNew */}
      <Route
        path="/admin/time-slots"
        element={
          <ProtectedRoute allowedRoles={['school_principal', 'school_admin', 'school_sub_admin']}>
            <TimeSlotsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/teacher-assignments"
        element={
          <ProtectedRoute allowedRoles={['school_principal', 'school_admin', 'school_sub_admin']}>
            <TeacherAssignmentsPage />
          </ProtectedRoute>
        }
      />

      {/* Teacher Attendance Management - For School Principal */}
      <Route
        path="/admin/teacher-attendance"
        element={
          <ProtectedRoute allowedRoles={['school_principal', 'school_admin', 'school_sub_admin']}>
            <TeacherAttendancePage />
          </ProtectedRoute>
        }
      />

      {/* School Principal Settings & Reports */}
      <Route
        path="/principal/settings"
        element={
          <ProtectedRoute allowedRoles={['school_principal', 'school_admin', 'school_sub_admin']}>
            <SchoolSettingsPagePro />
          </ProtectedRoute>
        }
      />
      <Route
        path="/school/settings"
        element={
          <ProtectedRoute allowedRoles={['school_principal', 'school_admin', 'school_sub_admin']}>
            <SchoolSettingsPagePro />
          </ProtectedRoute>
        }
      />
      <Route
        path="/school/academic-structure"
        element={<Navigate to="/school/settings?section=academic" replace />}
      />
      <Route
        path="/principal/academic-structure"
        element={<Navigate to="/school/settings?section=academic" replace />}
      />
      <Route
        path="/principal/timetable"
        element={
          <ProtectedRoute allowedRoles={['school_principal', 'school_admin', 'school_sub_admin']}>
            <PrincipalTimetablePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/school/teacher-class-assignments"
        element={
          <ProtectedRoute allowedRoles={['school_principal', 'school_admin', 'school_sub_admin']}>
            <TeacherClassAssignmentPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/principal/reports"
        element={
          <ProtectedRoute allowedRoles={['school_principal', 'school_admin', 'school_sub_admin']}>
            <SchoolReportsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/principal/ai-insights"
        element={
          <ProtectedRoute allowedRoles={['school_principal', 'school_admin', 'school_sub_admin']}>
            <AIInsightsPage />
          </ProtectedRoute>
        }
      />
      
      {/* Account Settings - All authenticated users */}
      <Route
        path="/account/settings"
        element={
          <ProtectedRoute allowedRoles={['platform_admin', 'school_principal', 'school_admin', 'school_sub_admin', 'teacher', 'student', 'parent']}>
            <AccountSettingsPage />
          </ProtectedRoute>
        }
      />

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <AuthProvider>
          <WebSocketProvider>
            <NassaqAlertProvider>
              <BrowserRouter>
                <AppRoutes />
                <Toaster position="top-center" richColors />
              </BrowserRouter>
            </NassaqAlertProvider>
          </WebSocketProvider>
        </AuthProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
