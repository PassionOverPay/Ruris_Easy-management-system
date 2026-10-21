import { Navigate, Route, Routes } from "react-router-dom";
import ProtectedRoute, { homeForRoles } from "./auth/ProtectedRoute";
import { useAuth } from "./auth/AuthContext";
import DepartmentHome from "./pages/DepartmentHome";
import Login from "./pages/Login";
import History from "./pages/History";

function HomeRedirect() {
  const { user, loading } = useAuth();
  if (loading) {
    return <main className="loading-screen">Loading your workspace…</main>;
  }
  return <Navigate to={user ? homeForRoles(user.roles) : "/login"} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/history" element={<History />} />
        <Route element={<ProtectedRoute allowedRoles={["admin"]} />}>
          <Route path="/admin" element={<DepartmentHome role="admin" />} />
        </Route>
        <Route element={<ProtectedRoute allowedRoles={["purchasing", "admin"]} />}>
          <Route
            path="/purchasing"
            element={<DepartmentHome role="purchasing" />}
          />
        </Route>
        <Route element={<ProtectedRoute allowedRoles={["warehouse", "admin"]} />}>
          <Route
            path="/warehouse"
            element={<DepartmentHome role="warehouse" />}
          />
        </Route>
        <Route element={<ProtectedRoute allowedRoles={["accounting", "admin"]} />}>
          <Route
            path="/accounting"
            element={<DepartmentHome role="accounting" />}
          />
        </Route>
      </Route>
      <Route path="/" element={<HomeRedirect />} />
      <Route path="*" element={<HomeRedirect />} />
    </Routes>
  );
}
