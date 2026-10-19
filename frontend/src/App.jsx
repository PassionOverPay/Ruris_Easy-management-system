import { Navigate, Route, Routes } from "react-router-dom";
import ProtectedRoute from "./auth/ProtectedRoute";
import { useAuth } from "./auth/AuthContext";
import DepartmentHome from "./pages/DepartmentHome";
import Login from "./pages/Login";

function HomeRedirect() {
  const { user, loading } = useAuth();
  if (loading) {
    return <main className="loading-screen">Loading your workspace…</main>;
  }
  return <Navigate to={user ? `/${user.role}` : "/login"} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<ProtectedRoute allowedRole="admin" />}>
          <Route path="/admin" element={<DepartmentHome role="admin" />} />
        </Route>
        <Route element={<ProtectedRoute allowedRole="purchasing" />}>
          <Route
            path="/purchasing"
            element={<DepartmentHome role="purchasing" />}
          />
        </Route>
        <Route element={<ProtectedRoute allowedRole="warehouse" />}>
          <Route
            path="/warehouse"
            element={<DepartmentHome role="warehouse" />}
          />
        </Route>
        <Route element={<ProtectedRoute allowedRole="accounting" />}>
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
