import { Navigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";

const ROLE_DASHBOARDS = {
  platform_admin: "/admin",
  school_principal: "/principal",
  school_sub_admin: "/school",
  school_admin: "/principal",
  platform_operations_manager: "/admin",
  teacher: "/teacher",
  student: "/student",
  parent: "/parent",
};

const LoadingSpinner = () => (
  <div className="min-h-screen flex items-center justify-center">
    <div className="animate-pulse text-brand-navy">جاري التحميل...</div>
  </div>
);

export const ProtectedRoute = ({ children, allowedRoles, skipPasswordCheck = false }) => {
  const { user, loading, isAuthenticated, isImpersonating, getEffectiveRole } = useAuth();

  if (loading) return <LoadingSpinner />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;

  if (!skipPasswordCheck && user?.must_change_password) {
    return <Navigate to="/change-password" replace />;
  }

  const effectiveRole = getEffectiveRole ? getEffectiveRole() : user?.role;

  if (allowedRoles && !allowedRoles.includes(effectiveRole)) {
    const target = ROLE_DASHBOARDS[effectiveRole] || "/";
    return <Navigate to={target} replace />;
  }

  return children;
};

export const PublicRoute = ({ children }) => {
  const { user, loading, isAuthenticated } = useAuth();

  if (loading) return <LoadingSpinner />;

  if (isAuthenticated) {
    const target = ROLE_DASHBOARDS[user?.role] || "/";
    return <Navigate to={target} replace />;
  }

  return children;
};
