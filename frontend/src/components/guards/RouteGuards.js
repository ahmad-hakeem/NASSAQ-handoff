import { useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";

export const ROLE_DASHBOARDS = {
  platform_admin: "/admin",
  school_principal: "/principal",
  school_sub_admin: "/school",
  school_admin: "/principal",
  platform_operations_manager: "/admin",
  teacher: "/teacher",
  independent_teacher: "/teacher",
  student: "/student",
  parent: "/parent",
};

const LoadingSpinner = () => (
  <div className="min-h-screen flex items-center justify-center">
    <div className="animate-pulse text-brand-navy">جاري التحميل...</div>
  </div>
);

// Walk a permissions payload and return true if `key` (e.g.
// "students.bulk_import_workspace") is granted. Tolerates either an
// array of permission strings or a nested object map (the
// /auth/me/permissions response shape may evolve).
const hasPermission = (permissions, key) => {
  if (!permissions || !key) return false;
  if (Array.isArray(permissions)) return permissions.includes(key);
  if (typeof permissions === "object") {
    if (Array.isArray(permissions.permissions)) {
      return permissions.permissions.includes(key);
    }
    const [group, leaf] = key.split(".");
    const bucket = permissions[group];
    if (Array.isArray(bucket)) return bucket.includes(leaf);
    if (bucket && typeof bucket === "object") return !!bucket[leaf];
    return !!permissions[key];
  }
  return false;
};

export const ProtectedRoute = ({
  children,
  allowedRoles,
  requiredPermission,
  skipPasswordCheck = false,
}) => {
  const {
    user, loading, isAuthenticated, getEffectiveRole,
    permissions, fetchPermissions,
  } = useAuth();
  const location = useLocation();
  const [permsResolved, setPermsResolved] = useState(!requiredPermission);

  useEffect(() => {
    if (!requiredPermission) { setPermsResolved(true); return; }
    if (permissions) { setPermsResolved(true); return; }
    let cancelled = false;
    (async () => {
      try { await fetchPermissions?.(); } finally {
        if (!cancelled) setPermsResolved(true);
      }
    })();
    return () => { cancelled = true; };
  }, [requiredPermission, permissions, fetchPermissions]);

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

  // Pre-bootstrap Independent Teacher (no workspace yet) must land on the
  // onboarding wizard before any other /teacher/* surface mounts. The wizard
  // itself triggers MFA step-up via the AuthContext axios interceptor when
  // it submits to the bootstrap endpoint, so we don't need a dedicated MFA
  // route here. Allow the wizard, the change-password shim, and any future
  // /auth/mfa/* surface to render without a redirect loop.
  if (
    effectiveRole === "independent_teacher" &&
    !user?.tenant_id &&
    location.pathname !== "/teacher/onboarding" &&
    !location.pathname.startsWith("/auth/mfa") &&
    location.pathname !== "/change-password"
  ) {
    return <Navigate to="/teacher/onboarding" replace />;
  }

  if (requiredPermission) {
    if (!permsResolved) return <LoadingSpinner />;
    if (!hasPermission(permissions, requiredPermission)) {
      const target = ROLE_DASHBOARDS[effectiveRole] || "/";
      return <Navigate to={target} replace />;
    }
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
