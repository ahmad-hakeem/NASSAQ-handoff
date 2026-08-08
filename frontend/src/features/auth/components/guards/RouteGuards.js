import { useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/shared/contexts/AuthContext";
import ParentCharterModal from "@/features/parent-portal/components/parent/ParentCharterModal";
import { LoadingState } from "@/shared/components/ui/LoadingState";

export const ROLE_DASHBOARDS = {
  platform_admin: "/admin",
  school_principal: "/principal",
  school_sub_admin: "/school",
  school_admin: "/principal",
  platform_operations_manager: "/admin",
  platform_sub_admin: "/admin",
  teacher: "/teacher",
  independent_teacher: "/teacher",
  // Student portal is temporarily disabled platform-wide. Mapping the
  // student role to "/login" instead of "/student" prevents the
  // PublicRoute → ProtectedRoute bounce that would otherwise pingpong
  // an authenticated student session between /login and /student now
  // that /student/* is a Navigate-to-/login redirect.
  student: "/login",
  parent: "/parent",
};

const LoadingSpinner = () => (
  <LoadingState variant="fullpage" className="min-h-screen" />
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
  // Demo kill switch — when the backend reports
  // ``mfa_enforcement_disabled`` we mirror that here by skipping the
  // ``/auth/mfa/enroll`` redirect for IT, teachers, and parents.
  // Bootstrap (no tenant_id yet) still routes IT users through the
  // onboarding wizard so workspace materialisation still completes.
  const mfaDisabled = !!user?.mfa_enforcement_disabled;
  if (
    effectiveRole === "independent_teacher" &&
    location.pathname !== "/change-password"
  ) {
    if (!mfaDisabled && !user?.mfa_enrolled_at && !location.pathname.startsWith("/auth/mfa")) {
      return <Navigate to="/auth/mfa/enroll" replace />;
    }
    if (
      (mfaDisabled || user?.mfa_enrolled_at) &&
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
  // backend/routes/auth_routes_mod.py login gate).
  // Task #443: the backend now enforces this server-side — get_current_user
  // returns HTTP 403 mfa_enrollment_required for any unenrolled Tier A/B/C
  // user calling a non-/auth/mfa* route. This guard is kept as a UX layer
  // so deep-links redirect immediately without a round-trip to the server.
  if (
    effectiveRole === "teacher" &&
    !mfaDisabled &&
    !user?.mfa_enrolled_at &&
    location.pathname !== "/change-password" &&
    !location.pathname.startsWith("/auth/mfa")
  ) {
    return <Navigate to="/auth/mfa/enroll" replace />;
  }

  // 2026 - Parents (Tier C) follow the same rule as Tier B teachers.
  // Email OTP was removed as the mandatory parent login factor (see
  // backend/services/mfa_policy.py and the login gate in
  // backend/routes/auth_routes_mod.py). The backend mints a normal
  // access token for an unenrolled parent so this guard mirrors the
  // contract and prevents deep-links bypassing the enrolment screen.
  if (
    effectiveRole === "parent" &&
    !mfaDisabled &&
    !user?.mfa_enrolled_at &&
    location.pathname !== "/change-password" &&
    !location.pathname.startsWith("/auth/mfa")
  ) {
    return <Navigate to="/auth/mfa/enroll" replace />;
  }

  // Mandatory Parent Charter (ميثاق ولي الأمر) blocking guard.
  // Every authenticated parent must explicitly accept the charter
  // before reaching any /parent/* surface. The check runs AFTER the
  // password and MFA gates so a parent who still has those pending
  // sees them first, but it deliberately runs BEFORE the permission
  // check so a deep-link to a permissioned page (or any future child
  // route) cannot bypass the charter. Backward-compat: existing
  // parents have charter_accepted_at = NULL and will be intercepted
  // on their next request.
  if (effectiveRole === "parent" && !user?.charter_accepted_at) {
    return <ParentCharterModal />;
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
