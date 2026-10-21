import { useState } from "react";
import { Link, NavLink } from "react-router-dom";
import api from "../api/axios";
import { useAuth } from "../auth/AuthContext";
import CreatePOForm from "../components/CreatePOForm";
import CreateReceiptForm from "../components/CreateReceiptForm";
import InvoiceProcessing from "../components/InvoiceProcessing";
import POHistoryTable from "../components/POHistoryTable";
import ReceiptsHistoryTable from "../components/ReceiptsHistoryTable";
import InvoicesHistoryTable from "../components/InvoicesHistoryTable";
import UserManagement from "../components/UserManagement";

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

const navigationRoles = {
  admin: ["admin"],
  purchasing: ["purchasing", "admin"],
  warehouse: ["warehouse", "admin"],
  accounting: ["accounting", "admin"],
};

export default function DepartmentHome({ role }) {
  const { user, logout } = useAuth();
  const content = departmentContent[role];
  const [newUser, setNewUser] = useState({
    email: "",
    full_name: "",
    password: "",
    roles: ["purchasing"],
  });
  const [provisionMessage, setProvisionMessage] = useState("");
  const [provisionError, setProvisionError] = useState("");
  const [creatingUser, setCreatingUser] = useState(false);
  const [usersRefreshKey, setUsersRefreshKey] = useState(0);

  async function handleProvision(event) {
    event.preventDefault();
    setProvisionMessage("");
    setProvisionError("");
    setCreatingUser(true);
    try {
      await api.post("/api/v1/admin/users", newUser);
      setProvisionMessage(`Account created for ${newUser.email}.`);
      setUsersRefreshKey((key) => key + 1);
      setNewUser({
        email: "",
        full_name: "",
        password: "",
        roles: ["purchasing"],
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
        <nav aria-label="Workspace navigation" className="workspace-navigation">
            {Object.entries(departmentContent)
              .filter(([department]) =>
                user.roles.some((userRole) =>
                  navigationRoles[department].includes(userRole),
                ),
              )
              .map(([department, details]) => (
              <NavLink
                key={department}
                className={({ isActive }) =>
                  `workspace-nav-link${isActive ? " active" : ""}`
                }
                to={`/${department}`}
              >
                {details.title}
              </NavLink>
            ))}
            <NavLink
              className={({ isActive }) =>
                `workspace-nav-link${isActive ? " active" : ""}`
              }
              to="/history"
            >
              History
            </NavLink>
        </nav>
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
        {role === "purchasing" && (
          <>
            <CreatePOForm />
            <POHistoryTable />
          </>
        )}
        {role === "warehouse" && (
          <>
            <CreateReceiptForm />
            <ReceiptsHistoryTable />
          </>
        )}
        {role === "accounting" && (
          <>
            <InvoiceProcessing />
            <InvoicesHistoryTable />
          </>
        )}
        {role === "admin" && (
          <>
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
              <fieldset className="role-options">
                <legend>Department roles</legend>
                {[
                  ["purchasing", "Purchasing"],
                  ["warehouse", "Warehouse"],
                  ["accounting", "Accounting"],
                ].map(([value, label]) => (
                  <label className="role-option" key={value}>
                    <input
                      checked={newUser.roles.includes(value)}
                      onChange={(event) => {
                        const roles = event.target.checked
                          ? [...newUser.roles, value]
                          : newUser.roles.filter((roleName) => roleName !== value);
                        setNewUser({ ...newUser, roles });
                      }}
                      type="checkbox"
                      value={value}
                    />
                    {label}
                  </label>
                ))}
              </fieldset>
              {newUser.roles.length === 0 && (
                <p className="form-error" role="alert">
                  Choose at least one department role.
                </p>
              )}
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
              <button
                disabled={creatingUser || newUser.roles.length === 0}
                type="submit"
              >
                {creatingUser ? "Creating account…" : "Create account"}
              </button>
            </form>
            <UserManagement refreshKey={usersRefreshKey} />
          </>
        )}
      </section>
    </main>
  );
}
