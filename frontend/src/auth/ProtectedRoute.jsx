import { Link, Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";

export const roleHome = {
  admin: "/admin",
  purchasing: "/purchasing",
  warehouse: "/warehouse",
  accounting: "/accounting",
};

export default function ProtectedRoute({ allowedRole }) {
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
  if (allowedRole && user.role !== allowedRole) {
    return <Navigate to={roleHome[user.role] || "/login"} replace />;
  }
  return <Outlet />;
}
