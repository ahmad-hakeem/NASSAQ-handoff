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

  // Spec §5.1 first-login orchestration for Independent Teacher accounts:
  //   signup → MFA enrolment → recent assertion → wizard → bootstrap.
  // The bootstrap endpoint hard-requires `users.mfa_enrolled_at`, so an IT
  // user without MFA must land on /auth/mfa/enroll FIRST; only after MFA is
  // enrolled may they reach the wizard. Once bootstrapped (tenant_id set)
  // they get the regular /teacher surface. Allow /change-password as a
  // permitted detour from either gate.
  if (
    effectiveRole === "independent_teacher" &&
    location.pathname !== "/change-password"
  ) {
    if (!user?.mfa_enrolled_at && !location.pathname.startsWith("/auth/mfa")) {
      return <Navigate to="/auth/mfa/enroll" replace />;
    }
    if (
      user?.mfa_enrolled_at &&
      !user?.tenant_id &&
      location.pathname !== "/teacher/onboarding" &&
      !location.pathname.startsWith("/auth/mfa")
    ) {
      return <Navigate to="/teacher/onboarding" replace />;
    }
  }

  // 2026-05-13 — School teachers (Tier B) must enrol an authenticator
  // factor before reaching the dashboard. Email OTP was removed as a
  // mandatory login factor (see backend/services/mfa_policy.py and
  // backend/routes/auth_routes_mod.py login gate). The backend mints a
  // normal access token for an unenrolled teacher and this guard mirrors
  // that contract so a deep-link cannot bypass the enrolment screen.
  if (
    effectiveRole === "teacher" &&
    !user?.mfa_enrolled_at &&
    location.pathname !== "/change-password" &&
    !location.pathname.startsWith("/auth/mfa")
  ) {
    return <Navigate to="/auth/mfa/enroll" replace />;
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
