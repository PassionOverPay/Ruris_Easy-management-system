import { useState } from "react";
import { Link } from "react-router-dom";
import api from "../api/axios";
import { useAuth } from "../auth/AuthContext";

const departmentContent = {
  admin: {
    title: "Administration",
    description: "Provision and manage access for your department teams.",
  },
  purchasing: {
    title: "Purchasing",
    description: "Track purchase orders and expected deliveries.",
  },
  warehouse: {
    title: "Warehouse",
    description: "Record incoming shipments and delivery discrepancies.",
  },
  accounting: {
    title: "Accounting",
    description: "Review invoices against purchase orders and receipts.",
  },
};

export default function DepartmentHome({ role }) {
  const { user, logout } = useAuth();
  const content = departmentContent[role];
  const [newUser, setNewUser] = useState({
    email: "",
    full_name: "",
    password: "",
    role: "purchasing",
  });
  const [provisionMessage, setProvisionMessage] = useState("");
  const [provisionError, setProvisionError] = useState("");
  const [creatingUser, setCreatingUser] = useState(false);

  async function handleProvision(event) {
    event.preventDefault();
    setProvisionMessage("");
    setProvisionError("");
    setCreatingUser(true);
    try {
      await api.post("/api/v1/admin/users", newUser);
      setProvisionMessage(`Account created for ${newUser.email}.`);
      setNewUser({
        email: "",
        full_name: "",
        password: "",
        role: "purchasing",
      });
    } catch (error) {
      const status = error.response?.status;
      setProvisionError(
        status === 409
          ? "An account with this email already exists."
          : "The account could not be created. Check your access and try again.",
      );
    } finally {
      setCreatingUser(false);
    }
  }

  return (
    <main className="workspace-page">
      <header className="workspace-header">
        <Link aria-label="Supply Chain Workspace home" className="workspace-brand" to="/">
          <span className="brand-mark small">SC</span>
          <span>Supply Chain</span>
        </Link>
        <div className="user-menu">
          <span>{user.full_name}</span>
          <button className="text-button" onClick={logout} type="button">
            Sign out
          </button>
        </div>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">{role.toUpperCase()} WORKSPACE</p>
        <h1>{content.title}</h1>
        <p>{content.description}</p>
        {role === "admin" && (
          <form className="provision-form" onSubmit={handleProvision}>
            <h2>Create a team account</h2>
            <label htmlFor="new-user-name">Full name</label>
            <input
              autoComplete="name"
              id="new-user-name"
              maxLength={255}
              onChange={(event) =>
                setNewUser({ ...newUser, full_name: event.target.value })
              }
              required
              value={newUser.full_name}
            />
            <label htmlFor="new-user-email">Work email</label>
            <input
              autoComplete="email"
              id="new-user-email"
              onChange={(event) =>
                setNewUser({ ...newUser, email: event.target.value })
              }
              required
              type="email"
              value={newUser.email}
            />
            <label htmlFor="new-user-password">Temporary password</label>
            <input
              autoComplete="new-password"
              id="new-user-password"
              onChange={(event) =>
                setNewUser({ ...newUser, password: event.target.value })
              }
              required
              type="password"
              value={newUser.password}
            />
            <label htmlFor="new-user-role">Department</label>
            <select
              id="new-user-role"
              onChange={(event) =>
                setNewUser({ ...newUser, role: event.target.value })
              }
              value={newUser.role}
            >
              <option value="purchasing">Purchasing</option>
              <option value="warehouse">Warehouse</option>
              <option value="accounting">Accounting</option>
            </select>
            {provisionError && (
              <p className="form-error" role="alert">
                {provisionError}
              </p>
            )}
            {provisionMessage && (
              <p className="form-success" role="status">
                {provisionMessage}
              </p>
            )}
            <button disabled={creatingUser} type="submit">
              {creatingUser ? "Creating account…" : "Create account"}
            </button>
          </form>
        )}
      </section>
    </main>
  );
}
