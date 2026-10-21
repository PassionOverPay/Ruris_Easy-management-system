import { useEffect, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import api from "../api/axios";
import { useAuth } from "../auth/AuthContext";

const departmentLabels = {
  admin: "Administration",
  purchasing: "Purchasing",
  warehouse: "Warehouse",
  accounting: "Accounting",
};

function formatTimestamp(value) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export default function History() {
  const { user, logout } = useAuth();
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    api.get("/api/v1/history")
      .then(({ data }) => {
        if (active) setEntries(data);
      })
      .catch(() => {
        if (active) setError("Activity history could not be loaded. Please try again.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  const home = user.roles.includes("admin")
    ? "/admin"
    : `/${user.roles.find((role) => role in departmentLabels) || "purchasing"}`;

  return (
    <main className="workspace-page">
      <header className="workspace-header">
        <Link aria-label="Supply Chain Workspace home" className="workspace-brand" to={home}>
          <span className="brand-mark small">SC</span>
          <span>Supply Chain</span>
        </Link>
        <nav aria-label="Workspace navigation" className="workspace-navigation">
          {user.roles.filter((role) => role in departmentLabels).map((role) => (
            <NavLink className="workspace-nav-link" key={role} to={`/${role}`}>
              {departmentLabels[role]}
            </NavLink>
          ))}
          <NavLink className={({ isActive }) => `workspace-nav-link${isActive ? " active" : ""}`} to="/history">
            History
          </NavLink>
        </nav>
        <div className="user-menu">
          <span>{user.full_name}</span>
          <button className="text-button" onClick={logout} type="button">Sign out</button>
        </div>
      </header>
      <section className="workspace-content history-content">
        <p className="eyebrow">SHARED ACTIVITY</p>
        <h1>History</h1>
        <p>See who did what and when across the supply workflow. Each entry names the person, action, record and time it was recorded.</p>

        <div className="history-guide">
          <h2>How to read this history</h2>
          <p><strong>Who</strong> is the signed-in account that performed the action. <strong>What</strong> describes the action and the affected record. <strong>When</strong> is the time the application recorded it, shown in your local time zone.</p>
          <p>History currently includes successful sign-ins, purchase orders, goods receipts, invoices, order matching reviews and user account administration. It shows the latest 200 recorded events.</p>
        </div>

        <section aria-labelledby="activity-heading" className="history-panel">
          <div className="history-panel-heading">
            <div>
              <h2 id="activity-heading">Recent activity</h2>
              <p>Newest events appear first.</p>
            </div>
            {!loading && !error && <span className="history-count">{entries.length} {entries.length === 1 ? "event" : "events"}</span>}
          </div>
          {loading && <p className="history-state" role="status">Loading activity…</p>}
          {error && <p className="history-state form-error" role="alert">{error}</p>}
          {!loading && !error && entries.length === 0 && (
            <p className="history-state">No activity has been recorded yet.</p>
          )}
          {!loading && !error && entries.length > 0 && (
            <ol className="history-list">
              {entries.map((entry) => (
                <li className="history-entry" key={entry.id}>
                  <span aria-hidden="true" className="history-dot" />
                  <div className="history-event">
                    <p className="history-description">{entry.description}</p>
                    <p className="history-actor">{entry.actor_name} <span>·</span> {entry.actor_roles.map((role) => departmentLabels[role] || role).join(", ")}</p>
                  </div>
                  <time className="history-time" dateTime={entry.timestamp}>{formatTimestamp(entry.timestamp)}</time>
                </li>
              ))}
            </ol>
          )}
        </section>
      </section>
    </main>
  );
}
