import { Link, Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";

export const roleHome = {
  admin: "/admin",
  purchasing: "/purchasing",
  warehouse: "/warehouse",
  accounting: "/accounting",
};

export function homeForRoles(roles = []) {
  if (roles.includes("admin")) return roleHome.admin;
  const departmentRole = roles.find((role) => role in roleHome);
  return departmentRole ? roleHome[departmentRole] : "/login";
}

export default function ProtectedRoute({ allowedRoles }) {
  const { user, loading, authError, refreshUser } = useAuth();
  const location = useLocation();

  if (loading) {
    return <main className="loading-screen">Loading your workspace…</main>;
  }
  if (authError) {
    return (
      <main className="loading-screen auth-error-screen">
        <p role="alert">{authError}</p>
        <button onClick={refreshUser} type="button">
          Try again
        </button>
        <Link to="/login">Sign in</Link>
      </main>
    );
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  if (
    allowedRoles &&
    !user.roles.some((role) => allowedRoles.includes(role))
  ) {
    return <Navigate to={homeForRoles(user.roles)} replace />;
  }
  return <Outlet />;
}
