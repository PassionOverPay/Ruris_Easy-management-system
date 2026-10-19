import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import api from "../api/axios";

const AuthContext = createContext(null);

function rolesFromToken(token) {
  try {
    const payloadPart = token.split(".")[1];
    if (!payloadPart) return [];

    const base64 = payloadPart.replace(/-/g, "+").replace(/_/g, "/");
    const payload = JSON.parse(
      decodeURIComponent(
        atob(base64)
          .split("")
          .map((character) =>
            `%${character.charCodeAt(0).toString(16).padStart(2, "0")}`,
          )
          .join(""),
      ),
    );
    return Array.isArray(payload.roles)
      ? payload.roles.filter((role) => typeof role === "string")
      : [];
  } catch {
    return [];
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState("");

  const loadUser = useCallback(async () => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      setUser(null);
      setAuthError("");
      setLoading(false);
      return;
    }

    setAuthError("");
    setLoading(true);
    try {
      const response = await api.get("/api/v1/users/me");
      const tokenRoles = rolesFromToken(token);
      setUser({
        ...response.data,
        roles: tokenRoles.length > 0 ? tokenRoles : response.data.roles,
      });
    } catch (error) {
      setUser(null);
      if (error.response?.status === 401) {
        localStorage.removeItem("access_token");
      } else {
        setAuthError("We couldn't verify your session. Check your connection.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadUser();
    const handleExpired = () => {
      setUser(null);
      setAuthError("");
      setLoading(false);
    };
    window.addEventListener("auth:expired", handleExpired);
    return () => window.removeEventListener("auth:expired", handleExpired);
  }, [loadUser]);

  const login = useCallback(async (email, password) => {
    const form = new URLSearchParams({ username: email, password });
    const tokenResponse = await api.post("/token", form, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
    const token = tokenResponse.data.access_token;
    localStorage.setItem("access_token", token);
    setAuthError("");
    try {
      const userResponse = await api.get("/api/v1/users/me");
      const tokenRoles = rolesFromToken(token);
      const signedInUser = {
        ...userResponse.data,
        roles: tokenRoles.length > 0 ? tokenRoles : userResponse.data.roles,
      };
      setUser(signedInUser);
      return signedInUser;
    } catch (error) {
      localStorage.removeItem("access_token");
      setUser(null);
      setAuthError("The account was authenticated, but its profile couldn't load.");
      throw error;
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("access_token");
    setUser(null);
    setAuthError("");
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      authError,
      login,
      logout,
      refreshUser: loadUser,
    }),
    [user, loading, authError, login, logout, loadUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
