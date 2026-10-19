import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { homeForRoles, roleHome } from "../auth/ProtectedRoute";
import { useAuth } from "../auth/AuthContext";

export default function Login() {
  const { user, authError, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (user) {
    return <Navigate to={homeForRoles(user.roles)} replace />;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const signedInUser = await login(email.trim(), password);
      const requestedPath = location.state?.from?.pathname;
      const requestedRole = Object.keys(roleHome).find(
        (role) => roleHome[role] === requestedPath,
      );
      const destination =
        requestedPath &&
        requestedRole &&
        (signedInUser.roles.includes(requestedRole) ||
          signedInUser.roles.includes("admin"))
          ? requestedPath
          : homeForRoles(signedInUser.roles);
      navigate(destination, { replace: true });
    } catch (loginError) {
      const status = loginError.response?.status;
      setError(
        status === 401
          ? "The email or password is incorrect."
          : "We couldn't sign you in. Check your connection and try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-panel" aria-labelledby="login-title">
        <div className="brand-mark" aria-hidden="true">
          SC
        </div>
        <p className="eyebrow">SUPPLY CHAIN WORKSPACE</p>
        <h1 id="login-title">Welcome back</h1>
        <p className="login-description">
          Sign in with the account provided by your administrator.
        </p>

        <form className="login-form" onSubmit={handleSubmit}>
          {authError && (
            <p className="form-error" role="alert">
              {authError}
            </p>
          )}
          <label htmlFor="email">Work email</label>
          <input
            autoComplete="username"
            id="email"
            name="email"
            onChange={(event) => setEmail(event.target.value)}
            placeholder="name@company.com"
            required
            type="email"
            value={email}
          />

          <label htmlFor="password">Password</label>
          <input
            autoComplete="current-password"
            id="password"
            name="password"
            onChange={(event) => setPassword(event.target.value)}
            required
            type="password"
            value={password}
          />

          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}

          <button disabled={submitting} type="submit">
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p className="login-footnote">Authorized team members only</p>
      </section>
      <aside className="login-aside" aria-label="Workspace overview">
        <div className="aside-content">
          <span className="aside-kicker">ONE CONNECTED WORKFLOW</span>
          <h2>From purchase order to verified invoice.</h2>
          <p>
            Keep purchasing, warehouse, and accounting aligned with a shared
            view of every delivery.
          </p>
          <div className="workflow">
            <span>Purchasing</span>
            <i />
            <span>Warehouse</span>
            <i />
            <span>Accounting</span>
          </div>
        </div>
        <span className="aside-index">01 / 03</span>
      </aside>
    </main>
  );
}
