import { useEffect, useMemo, useState } from "react";
import api from "../api/axios";

const roleStyles = {
  purchasing: "bg-blue-50 text-blue-700 ring-blue-600/20",
  warehouse: "bg-amber-50 text-amber-800 ring-amber-600/20",
  accounting: "bg-violet-50 text-violet-700 ring-violet-600/20",
  admin: "bg-emerald-50 text-emerald-800 ring-emerald-600/20",
};

export default function UserManagement({ refreshKey = 0 }) {
  const [users, setUsers] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    let active = true;

    async function loadUsers() {
      setLoading(true);
      setLoadError("");
      try {
        const response = await api.get("/api/v1/admin/users");
        if (active) setUsers(response.data);
      } catch {
        if (active) setLoadError("Accounts could not be loaded. Please try again.");
      } finally {
        if (active) setLoading(false);
      }
    }

    void loadUsers();
    return () => {
      active = false;
    };
  }, [refreshKey, retryKey]);

  const filteredUsers = useMemo(() => {
    const query = search.trim().toLocaleLowerCase();
    if (!query) return users;
    return users.filter(
      (user) =>
        user.full_name.toLocaleLowerCase().includes(query) ||
        user.email.toLocaleLowerCase().includes(query),
    );
  }, [search, users]);

  return (
    <section className="mt-8 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-col gap-4 border-b border-slate-200 px-5 py-5 sm:flex-row sm:items-end sm:justify-between sm:px-7">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-slate-900">
            User accounts
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Review account roles and status.
          </p>
        </div>
        <div className="w-full sm:max-w-xs">
          <label
            className="block text-sm font-medium text-slate-700"
            htmlFor="user-search"
          >
            Search users
          </label>
          <input
            className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-emerald-700 focus:ring-2 focus:ring-emerald-700/20"
            id="user-search"
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Name or email"
            type="search"
            value={search}
          />
        </div>
      </div>

      {loading ? (
        <p className="px-5 py-8 text-center text-sm text-slate-500" role="status">
          Loading user accounts…
        </p>
      ) : loadError ? (
        <div className="flex flex-col items-start gap-3 px-5 py-6">
          <p className="text-sm text-red-700" role="alert">
            {loadError}
          </p>
          <button
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            onClick={() => {
              setRetryKey((key) => key + 1);
            }}
            type="button"
          >
            Retry
          </button>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
              <tr>
                <th className="px-5 py-3 font-semibold sm:px-7" scope="col">
                  User
                </th>
                <th className="px-5 py-3 font-semibold" scope="col">
                  Roles
                </th>
                <th className="px-5 py-3 font-semibold" scope="col">
                  Status
                </th>
                <th className="px-5 py-3 font-semibold sm:pr-7" scope="col">
                  Created
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredUsers.map((user) => (
                <tr key={user.id}>
                  <td className="whitespace-nowrap px-5 py-4 sm:px-7">
                    <div className="font-medium text-slate-900">
                      {user.full_name}
                    </div>
                    <div className="mt-0.5 text-slate-500">{user.email}</div>
                  </td>
                  <td className="px-5 py-4">
                    <div className="flex flex-wrap gap-1.5">
                      {user.roles.map((role) => (
                        <span
                          className={`rounded-full px-2.5 py-1 text-xs font-semibold capitalize ring-1 ring-inset ${
                            roleStyles[role] || "bg-slate-100 text-slate-700 ring-slate-500/20"
                          }`}
                          key={role}
                        >
                          {role}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-5 py-4">
                    <span
                      className={
                        user.is_active
                          ? "rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-800"
                          : "rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600"
                      }
                    >
                      {user.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-5 py-4 text-slate-600 sm:pr-7">
                    {new Date(user.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
              {filteredUsers.length === 0 && (
                <tr>
                  <td
                    className="px-5 py-8 text-center text-slate-500 sm:px-7"
                    colSpan={4}
                  >
                    {users.length === 0
                      ? "No user accounts found."
                      : "No users match your search."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
